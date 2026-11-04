# Copyright 2025 ApeCloud, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import asyncio
import json
import logging
import time
import uuid
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from fastapi import WebSocket, WebSocketDisconnect

from aperag.agent import (
    AgentMessageQueue,
    format_invalid_json_error,
    format_invalid_model_spec_error,
    format_processing_error,
    format_query_required_error,
)
from aperag.agent.agent_event_listener import agent_event_listener
from aperag.agent.exceptions import AgentConfigurationError, JSONParsingError, handle_agent_error, safe_json_parse
from aperag.agent.response_types import AgentErrorResponse, AgentToolCallResultResponse
from aperag.schema import view_models
from aperag.service.prompt_template_service import prompt_template_service
from aperag.trace import add_trace_attributes, trace_async_function

if TYPE_CHECKING:
    from aperag.service.agent_chat_service import AgentChatService

logger = logging.getLogger(__name__)


def format_websocket_error(error: Exception, data: str) -> AgentErrorResponse:
    try:
        parsed = safe_json_parse(data, "language_detection")
        language = parsed.get("language", "en-US")
    except Exception:
        language = "en-US"

    if isinstance(error, JSONParsingError):
        return format_invalid_json_error(str(error), language)

    if isinstance(error, AgentConfigurationError):
        error_msg = str(error).lower()
        if "query" in error_msg:
            return format_query_required_error(language)
        if "completion" in error_msg or "modelspec" in error_msg:
            return format_invalid_model_spec_error(str(error), language)

    return format_processing_error(str(error), language)


class AgentChatWebSocket:
    def __init__(self, chat_service: "AgentChatService"):
        self.chat_service = chat_service

    def _parse_websocket_message(
        self, raw_data: str
    ) -> Tuple[Optional[view_models.AgentMessage], Optional[AgentErrorResponse]]:
        """
        Parse WebSocket message using Go-style error handling.

        Args:
            raw_data: Raw JSON string from WebSocket

        Returns:
            Tuple of (agent_message, error_response):
            - If successful: (agent_message, None)
            - If failed: (None, error_response_dict)
        """
        try:
            # Step 1: Safe JSON parsing using agent module utilities
            message_data = safe_json_parse(raw_data, "websocket_message")

            # Step 2: Validate required query field early
            action = message_data.get("action")
            if action in {"faq_expand", "faq_end"} and not message_data.get("query"):
                message_data["query"] = "是，专业扩展" if action == "faq_expand" else "否，结束"

            query = message_data.get("query", "").strip()
            if not query:
                from aperag.agent.exceptions import agent_config_invalid

                error = agent_config_invalid("query", "Query is required and cannot be empty")
                error_response = format_websocket_error(error, raw_data)
                return None, error_response

            # Step 3: Parse and validate AgentMessage using Pydantic
            agent_message = view_models.AgentMessage(**message_data)
            return agent_message, None

        except (JSONParsingError, AgentConfigurationError) as e:
            error_response = format_websocket_error(e, raw_data)
            return None, error_response
        except Exception as e:
            # Handle unexpected errors
            from aperag.agent.exceptions import agent_config_invalid

            config_error = agent_config_invalid("agent_message", f"Unexpected error: {str(e)}")
            error_response = format_websocket_error(config_error, raw_data)
            return None, error_response

    @handle_agent_error("websocket_agent_chat", reraise=False)
    async def handle_websocket_agent_chat(self, websocket: WebSocket, user: str, bot_id: str, chat_id: str):
        """Handle WebSocket connections for agent-type bot chats with message queue architecture"""
        # Get bot configuration once at the beginning for performance
        bot = await self.chat_service.db_ops.query_bot(user, bot_id)
        if not bot:
            error_response = format_processing_error("Bot not found", "en-US")
            await websocket.send_text(json.dumps(error_response))
            return

        # Parse bot configuration and get default collections once
        bot_config = None
        default_collections = []
        if bot.config:
            try:
                config_dict = json.loads(bot.config)
                if config_dict:
                    bot_config = view_models.BotConfig(**config_dict)
            except (json.JSONDecodeError, ValueError):
                bot_config = None

        if bot_config and bot_config.agent:
            # Get default collections once for performance
            if bot_config.agent.collections:
                collection_ids = [collection.id for collection in bot_config.agent.collections]
                db_collections = await self.chat_service.db_ops.query_collections_by_ids(user, collection_ids)
                # Convert SQLAlchemy models to Pydantic models
                default_collections = await self.chat_service._convert_db_collections_to_pydantic(db_collections)

        # Resolve prompts once at the beginning using prompt_template_service
        # Priority: Bot config > User default > System default > Hardcoded
        resolved_system_prompt = await prompt_template_service.resolve_agent_system_prompt(bot=bot, user_id=user)
        resolved_query_prompt = await prompt_template_service.resolve_agent_query_prompt(bot=bot, user_id=user)

        pending_messages = []
        while True:
            # Receive message from WebSocket
            try:
                data = pending_messages.pop(0) if pending_messages else await websocket.receive_text()
            except WebSocketDisconnect:
                return

            # Parse WebSocket message using Go-style error handling
            agent_message, error_response = self._parse_websocket_message(data)
            if error_response:
                await websocket.send_text(json.dumps(error_response))
                continue

            # Process each message in a new trace context
            try:
                await self._handle_single_message(
                    websocket,
                    agent_message,
                    user,
                    chat_id,
                    bot_config=bot_config,
                    default_collections=default_collections,
                    resolved_system_prompt=resolved_system_prompt,
                    resolved_query_prompt=resolved_query_prompt,
                    pending_messages=pending_messages,
                )
            except WebSocketDisconnect:
                return

    @trace_async_function("name=handle_single_websocket_message", new_trace=True)
    async def _handle_single_message(
        self,
        websocket: WebSocket,
        agent_message: view_models.AgentMessage,
        user: str,
        chat_id: str,
        bot_config=None,
        default_collections=None,
        resolved_system_prompt: str = None,
        resolved_query_prompt: str = None,
        pending_messages: Optional[List[str]] = None,
    ):
        """Handle a single WebSocket message with its own trace"""
        add_trace_attributes(
            **{"langfuse.session.id": chat_id, "langfuse.user.id": user, "langfuse.trace.name": "chat.message"}
        )
        trace_id = None
        message_id = None
        message_tasks = []
        if pending_messages is None:
            pending_messages = []
        started = time.perf_counter()
        try:
            message_id = str(uuid.uuid4())
            logger.info(
                "chat.message.started", extra={"message_id": message_id, "chat_id": chat_id, "status": "started"}
            )
            message_queue = AgentMessageQueue()
            trace_id = await self.chat_service.register_message_queue(agent_message.language, chat_id, message_id, message_queue)

            # Get document metadata and associate documents with message if files are provided
            from aperag.service.chat_document_service import chat_document_service

            document_ids = [file.id for file in agent_message.files or [] if file.id]
            files = await chat_document_service.associate_documents_with_message(
                chat_id=chat_id, message_id=message_id, files=document_ids, user=user
            )

            # Message Producer: Start background task to process agent generation message
            process_task = asyncio.create_task(
                self.chat_service.process_agent_message(
                    agent_message,
                    user,
                    chat_id,
                    message_id,
                    message_queue,
                    associated_files=files,
                    bot_config=bot_config,
                    default_collections=default_collections,
                    resolved_system_prompt=resolved_system_prompt,
                    resolved_query_prompt=resolved_query_prompt,
                )
            )
            message_tasks.append(process_task)
            # Message Consumer
            consumer_task = asyncio.create_task(self._consume_messages_from_queue(message_queue, websocket))
            message_tasks.append(consumer_task)

            async def watch_disconnect():
                # This is the only receiver while this message is being processed.
                # Preserve early next messages for the connection's outer loop.
                while True:
                    pending_messages.append(await websocket.receive_text())

            disconnect_task = asyncio.create_task(watch_disconnect())
            message_tasks.append(disconnect_task)
            pending = {process_task, consumer_task}
            while pending:
                done, _ = await asyncio.wait(pending | {disconnect_task}, return_when=asyncio.FIRST_COMPLETED)
                if disconnect_task in done:
                    await disconnect_task
                if any(task.cancelled() for task in done):
                    raise asyncio.CancelledError()
                pending.difference_update(done)
                if any(task.exception() is not None for task in done):
                    for task in pending:
                        task.cancel()
                    break
            process_result, consumer_result = await asyncio.gather(process_task, consumer_task, return_exceptions=True)
            # A disconnect may arrive while a failed task's sibling is stopping.
            if disconnect_task.done():
                await disconnect_task

            if isinstance(consumer_result, WebSocketDisconnect):
                raise consumer_result

            # Handle process_task exceptions with unified error formatting
            if isinstance(process_result, Exception):
                logger.error(
                    "chat.message.failed",
                    extra={
                        "message_id": message_id,
                        "chat_id": chat_id,
                        "stage": "chat.process",
                        "status": "failed",
                        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                    },
                    exc_info=(type(process_result), process_result, process_result.__traceback__),
                )
                error_response = self.chat_service._format_exception_to_error_response(
                    process_result, agent_message.language or "en-US"
                )
                await websocket.send_text(json.dumps(error_response))
                return

            # Handle consumer_task exceptions
            if isinstance(consumer_result, Exception):
                logger.error(
                    "chat.message.failed",
                    extra={
                        "message_id": message_id,
                        "chat_id": chat_id,
                        "stage": "chat.stream",
                        "status": "failed",
                        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                    },
                    exc_info=(type(consumer_result), consumer_result, consumer_result.__traceback__),
                )
                error_response = format_processing_error(str(consumer_result), agent_message.language or "en-US")
                await websocket.send_text(json.dumps(error_response))
                return

            # Handle history saving at WebSocket layer (better separation of concerns)
            # process_result now contains {query, content, references} on success
            query = process_result.get("query", "")
            ai_response = process_result.get("content", "")
            references = process_result.get("references", "")
            tool_use_list = consumer_result
            await self.chat_service._save_conversation_history(
                chat_id, message_id, trace_id, query, ai_response, files, tool_use_list, references
            )
            logger.info(
                "chat.message.completed",
                extra={
                    "message_id": message_id,
                    "chat_id": chat_id,
                    "status": "success",
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                },
            )

        except (asyncio.CancelledError, WebSocketDisconnect):
            logger.info(
                "chat.message.cancelled",
                extra={
                    "message_id": message_id,
                    "chat_id": chat_id,
                    "status": "cancelled",
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                },
            )
            raise
        except Exception as e:
            # This catches any other unexpected errors not handled above
            logger.exception(
                "chat.message.failed",
                extra={
                    "message_id": message_id,
                    "chat_id": chat_id,
                    "status": "failed",
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                },
            )
            error_response = format_processing_error(str(e), agent_message.language or "en-US")
            await websocket.send_text(json.dumps(error_response))
        finally:
            for task in message_tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*message_tasks, return_exceptions=True)
            if trace_id:
                await agent_event_listener.unregister_listener(str(trace_id))

    async def _stream_message_content(
        self, message: Dict[str, Any], websocket: WebSocket, chunk_size: int = 5, delay: float = 0.01
    ) -> None:
        """
        Stream message content in small chunks to simulate typing effect.

        Args:
            message: The message dict with type="message"
            websocket: WebSocket connection to send chunks
            chunk_size: Number of characters per chunk
            delay: Delay in seconds between chunks
        """
        content = message.get("data", "")
        if not content:
            # If no content, send the original message
            await websocket.send_text(json.dumps(message))
            return

        # Split content into chunks
        chunks = [content[i : i + chunk_size] for i in range(0, len(content), chunk_size)]

        for i, chunk in enumerate(chunks):
            # Create a chunk message with same structure but partial content
            chunk_message = {
                "type": "message",
                "id": message.get("id"),
                "data": chunk,
                "timestamp": message.get("timestamp", int(time.time())),
            }

            await websocket.send_text(json.dumps(chunk_message))
            logger.debug(f"Sent message chunk {i + 1}/{len(chunks)}: {len(chunk)} chars")

            # Add delay between chunks (except for the last one)
            if i < len(chunks) - 1:
                await asyncio.sleep(delay)

    async def _consume_messages_from_queue(
        self, message_queue: AgentMessageQueue, websocket: WebSocket
    ) -> List[AgentToolCallResultResponse]:
        """
        Consume messages from queue, send to WebSocket, and collect AgentToolCallResultResponse messages.

        This method runs as a separate task to avoid race conditions.
        Returns a list of all AgentToolCallResultResponse messages.
        """
        try:
            # Properly initialize list to collect AgentToolCallResultResponse messages
            tool_call_results: List[Dict] = []

            while True:
                # Get message from queue (blocks until message is available)
                message = await message_queue.get()

                # None message signals end of stream
                if message is None:
                    logger.debug("Received end-of-stream signal from message queue")
                    break

                # Collect AgentToolCallResultResponse messages
                if isinstance(message, dict) and message.get("type") == "tool_call_result":
                    tool_call_results.append(message)

                # Special handling for type="message" - stream it in chunks
                if isinstance(message, dict) and message.get("type") == "message":
                    await self._stream_message_content(message, websocket)
                    logger.debug(f"Streamed message content: {message.get('type', 'unknown')}")
                else:
                    # Send other message types normally (start, stop, tool_call_result, etc.)
                    await websocket.send_text(json.dumps(message))
                    logger.debug(f"Sent message to WebSocket: {message.get('type', 'unknown')}")

            return tool_call_results

        except WebSocketDisconnect:
            raise
        except Exception as e:
            logger.error(f"Error in message consumer: {e}")
            raise
