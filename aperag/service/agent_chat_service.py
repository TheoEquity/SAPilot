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
import os
import re
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from fastapi import WebSocket
from mcp_agent.workflows.llm.augmented_llm import RequestParams
from sqlalchemy.ext.asyncio import AsyncSession

from aperag.agent import (
    AgentHistoryManager,
    AgentMemoryManager,
    AgentMessageQueue,
    agent_session_manager,
    extract_tool_call_references,
    format_agent_setup_error,
    format_invalid_json_error,
    format_invalid_model_spec_error,
    format_mcp_connection_error,
    format_processing_error,
    format_query_required_error,
    format_stream_content,
    format_stream_end,
    format_stream_start,
)
from aperag.agent.agent_config import AgentConfig
from aperag.agent.agent_event_listener import agent_event_listener
from aperag.agent.exceptions import (
    AgentConfigurationError,
    JSONParsingError,
    MCPAppInitializationError,
    MCPConnectionError,
    handle_agent_error,
    safe_json_parse,
)
from aperag.agent.response_types import AgentErrorResponse, AgentToolCallResultResponse
from aperag.chat.history.message import StoredChatMessage, create_assistant_message
from aperag.config import settings
from aperag.db.ops import AsyncDatabaseOps, async_db_ops
from aperag.query.query import DocumentWithScore
from aperag.schema import view_models
from aperag.service.image_search_service import image_search_service
from aperag.service.prompt_template_service import build_agent_query_prompt, prompt_template_service
from aperag.trace import trace_async_function

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


class AgentChatService:
    """
    Chat service specifically for agent-type bots that uses MCPApp for intelligent conversation.

    This service uses AgentSessionManager for efficient session lifecycle management,
    including collection selection, model choice, and web search capabilities.

    Refactored to use message queue for clean separation of concerns.
    """

    def __init__(self, session: AsyncSession = None):
        if session is None:
            self.db_ops = async_db_ops
        else:
            self.db_ops = AsyncDatabaseOps(session)

        # Initialize memory and history managers
        self.memory_manager = AgentMemoryManager()
        self.history_manager = AgentHistoryManager()

    async def _convert_db_collections_to_pydantic(self, db_collections) -> List[view_models.Collection]:
        """Convert SQLAlchemy Collection models to Pydantic Collection models"""
        from aperag.schema.utils import parseCollectionConfig

        pydantic_collections = []
        for db_collection in db_collections:
            pydantic_collection = view_models.Collection(
                id=db_collection.id,
                title=db_collection.title,
                description=db_collection.description,
                type=db_collection.type,
                status=getattr(db_collection, "status", None),
                config=parseCollectionConfig(db_collection.config),
                created=db_collection.gmt_created.isoformat(),
                updated=db_collection.gmt_updated.isoformat(),
            )
            pydantic_collections.append(pydantic_collection)
        return pydantic_collections

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
        bot = await self.db_ops.query_bot(user, bot_id)
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
                db_collections = await self.db_ops.query_collections_by_ids(user, collection_ids)
                # Convert SQLAlchemy models to Pydantic models
                default_collections = await self._convert_db_collections_to_pydantic(db_collections)

        # Resolve prompts once at the beginning using prompt_template_service
        # Priority: Bot config > User default > System default > Hardcoded
        resolved_system_prompt = await prompt_template_service.resolve_agent_system_prompt(bot=bot, user_id=user)
        resolved_query_prompt = await prompt_template_service.resolve_agent_query_prompt(bot=bot, user_id=user)

        while True:
            # Receive message from WebSocket
            data = await websocket.receive_text()

            # Parse WebSocket message using Go-style error handling
            agent_message, error_response = self._parse_websocket_message(data)
            if error_response:
                await websocket.send_text(json.dumps(error_response))
                continue

            # Process each message in a new trace context
            await self._handle_single_message(
                websocket,
                agent_message,
                user,
                chat_id,
                bot_config=bot_config,
                default_collections=default_collections,
                resolved_system_prompt=resolved_system_prompt,
                resolved_query_prompt=resolved_query_prompt,
            )

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
    ):
        """Handle a single WebSocket message with its own trace"""
        trace_id = None
        try:
            message_id = str(uuid.uuid4())
            message_queue = AgentMessageQueue()
            trace_id = await self.register_message_queue(agent_message.language, chat_id, message_id, message_queue)

            # Get document metadata and associate documents with message if files are provided
            from aperag.service.chat_document_service import chat_document_service

            document_ids = [file.id for file in agent_message.files or [] if file.id]
            files = await chat_document_service.associate_documents_with_message(
                chat_id=chat_id, message_id=message_id, files=document_ids, user=user
            )

            # Message Producer: Start background task to process agent generation message
            process_task = asyncio.create_task(
                self.process_agent_message(
                    agent_message,
                    user,
                    chat_id,
                    message_id,
                    message_queue,
                    bot_config=bot_config,
                    default_collections=default_collections,
                    resolved_system_prompt=resolved_system_prompt,
                    resolved_query_prompt=resolved_query_prompt,
                )
            )
            # Message Consumer
            consumer_task = asyncio.create_task(self._consume_messages_from_queue(message_queue, websocket))
            process_result, consumer_result = await asyncio.gather(process_task, consumer_task, return_exceptions=True)

            # Handle process_task exceptions with unified error formatting
            if isinstance(process_result, Exception):
                logger.error(f"Process task failed: {process_result}")
                error_response = self._format_exception_to_error_response(
                    process_result, agent_message.language or "en-US"
                )
                await websocket.send_text(json.dumps(error_response))
                return

            # Handle consumer_task exceptions
            if isinstance(consumer_result, Exception):
                logger.error(f"Consumer task failed: {consumer_result}")
                error_response = format_processing_error(str(consumer_result), agent_message.language or "en-US")
                await websocket.send_text(json.dumps(error_response))
                return

            # Handle history saving at WebSocket layer (better separation of concerns)
            # process_result now contains {query, content, references} on success
            query = process_result.get("query", "")
            ai_response = process_result.get("content", "")
            references = process_result.get("references", "")
            tool_use_list = consumer_result
            await self._save_conversation_history(
                chat_id, message_id, trace_id, query, ai_response, files, tool_use_list, references
            )

        except Exception as e:
            # This catches any other unexpected errors not handled above
            logger.error(f"Unexpected error processing agent websocket message: {e}")
            error_response = format_processing_error(str(e), agent_message.language or "en-US")
            await websocket.send_text(json.dumps(error_response))
        finally:
            if trace_id:
                await agent_event_listener.unregister_listener(str(trace_id))

    async def register_message_queue(self, language, chat_id, message_id, message_queue):
        # Get the trace_id from the current span
        from aperag.trace.mcp_integration import get_current_trace_info

        trace_id, _ = get_current_trace_info()
        if not trace_id:
            logger.error("Could not get trace_id from current span, event dispatching will fail.")
        else:
            # Register a listener for this request with the global proxy.
            await agent_event_listener.register_listener(
                trace_id=str(trace_id),
                chat_id=chat_id,
                message_id=message_id,
                queue=message_queue,
                language=language,
            )
        return trace_id

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

        except Exception as e:
            logger.error(f"Error in message consumer: {e}")
            raise

    async def _get_agent_session(
        self, agent_message: view_models.AgentMessage, user: str, chat_id: str, resolved_system_prompt: str
    ):
        """Get or create chat session using AgentConfig."""
        # Query provider details and API key from database
        provider_info = await self.db_ops.query_llm_provider_by_name(agent_message.completion.model_service_provider)
        if not provider_info:
            error_msg = f"Provider '{agent_message.completion.model_service_provider}' not found in database"
            logger.error(error_msg)
            raise AgentConfigurationError(error_msg)

        api_key = await self.db_ops.query_provider_api_key(
            agent_message.completion.model_service_provider, user_id=user, need_public=True
        )
        if not api_key:
            error_msg = f"No API key available for provider '{agent_message.completion.model_service_provider}'"
            logger.error(error_msg)
            raise AgentConfigurationError(error_msg)

        aperag_api_keys = await self.db_ops.query_api_keys(user, is_system=True)
        for item in aperag_api_keys:
            aperag_api_key = item.key
        if not aperag_api_key:
            # Auto-create a new system aperag API key for the user if none exists
            logger.info(f"No aperag API key found for user {user}, creating a new system key")
            try:
                api_key_result = await self.db_ops.create_api_key(user=user, description="aperag", is_system=True)
                aperag_api_key = api_key_result.key
                logger.info(f"Successfully created new system aperag API key for user {user}")
            except Exception as e:
                error_msg = f"Failed to create aperag API key for user {user}: {str(e)}"
                logger.error(error_msg)
                raise AgentConfigurationError(error_msg)

        # Use resolved system prompt (already processed through prompt_template_service)
        system_prompt = resolved_system_prompt

        # Create AgentConfig with all needed parameters including chat_id
        config = AgentConfig(
            user_id=user,
            chat_id=chat_id,
            provider_name=agent_message.completion.model_service_provider,
            api_key=api_key,
            base_url=provider_info.base_url,
            default_model=agent_message.completion.model,
            language=agent_message.language if agent_message.language else "en-US",
            instruction=system_prompt,
            server_names=["aperag"],
            aperag_api_key=aperag_api_key,
            aperag_mcp_url=os.getenv("APERAG_MCP_URL", "http://localhost:8000/mcp/"),
            temperature=0.7,
            max_tokens=60000,
        )

        # Get or create chat session using config
        session = await agent_session_manager.get_or_create_session(config)

        return session

    async def process_agent_message(
        self,
        agent_message: view_models.AgentMessage,
        user: str,
        chat_id: str,
        message_id: str,
        message_queue: AgentMessageQueue,
        bot_config=None,
        default_collections=None,
        resolved_system_prompt: str = None,
        resolved_query_prompt: str = None,
    ) -> Dict[str, Any]:
        # Use pre-parsed configuration for performance
        # Priority: agent_message > bot_config > defaults
        final_completion = agent_message.completion
        final_collections = agent_message.collections

        # Use bot config as fallback for completion and collections
        if not final_completion and bot_config and bot_config.agent and bot_config.agent.completion:
            final_completion = bot_config.agent.completion

        if not final_collections and default_collections:
            final_collections = default_collections

        # Validate ModelSpec
        if not final_completion or not final_completion.model:
            raise AgentConfigurationError(
                config_key="completion.model", reason="Model specification is required for AI response generation"
            )

        # Create a new agent message with merged configuration
        merged_agent_message = view_models.AgentMessage(
            query=agent_message.query,
            collections=final_collections,
            completion=final_completion,
            web_search_enabled=agent_message.web_search_enabled,
            language=agent_message.language,
            files=agent_message.files,
            action=agent_message.action,
        )

        try:
            # Send start message
            await message_queue.put(format_stream_start(message_id))

            # Create memory from chat history
            history = await self.history_manager.get_chat_history(chat_id)
            memory = await self.memory_manager.create_memory_from_history(history, context_limit=4)

            if merged_agent_message.action == "faq_end":
                end_response = self._build_faq_choice_end_response(agent_message.language)
                await message_queue.put(format_stream_content(message_id, end_response))
                await message_queue.put(format_stream_end(message_id, references=[], urls=[]))
                return {
                    "query": merged_agent_message.query,
                    "content": end_response,
                    "references": [],
                }

            # Decide whether to search knowledge base based on trigger rules
            search_trigger = self._should_search_knowledge_base(
                query=merged_agent_message.query,
                files=merged_agent_message.files,
                memory=memory,
            )

            if not search_trigger:
                # Free conversation mode: LLM responds without search tools
                session = await self._get_agent_session(merged_agent_message, user, chat_id, resolved_system_prompt)
                llm = await session.get_llm(final_completion.model)
                llm.history = memory

                request_params = RequestParams(
                    maxTokens=8192,
                    model=final_completion.model,
                    use_history=True,
                    max_iterations=1,
                    temperature=0.7,
                    user=user,
                    tool_filter={"aperag": set()},
                )
                response = await llm.generate_str(merged_agent_message.query, request_params)
                full_content = response if response else "No response generated"

                await asyncio.sleep(0.1)
                await message_queue.put(format_stream_content(message_id, full_content))
                tool_references = extract_tool_call_references(llm.history)
                await message_queue.put(format_stream_end(message_id, references=tool_references, urls=[]))
                return {
                    "query": merged_agent_message.query,
                    "content": full_content,
                    "references": tool_references,
                }

            if search_trigger == "faq_end":
                end_response = self._build_faq_choice_end_response(agent_message.language)
                await message_queue.put(format_stream_content(message_id, end_response))
                await message_queue.put(format_stream_end(message_id, references=[], urls=[]))
                return {
                    "query": merged_agent_message.query,
                    "content": end_response,
                    "references": [],
                }

            # Knowledge base search mode: full MCP agent with search tools

            # Only allow expansion mode when triggered by expansion confirmation
            is_expert_expansion_confirmed = search_trigger == "expansion"

            # Get chat session using merged agent message and resolved system prompt
            session = await self._get_agent_session(merged_agent_message, user, chat_id, resolved_system_prompt)
            llm = await session.get_llm(final_completion.model)

            llm.history = memory

            original_user_query = merged_agent_message.query
            llm_agent_message = merged_agent_message

            if search_trigger == "kb_existence":
                llm_agent_message = merged_agent_message.model_copy(
                    update={"query": self._build_knowledge_base_existence_query(original_user_query)}
                )

            # Pre-execute image search only to identify the matched FAQ question text.
            image_search_results: List[DocumentWithScore] = []
            has_image_files = self._has_image_files(merged_agent_message.files)
            if has_image_files:
                image_search_results = await self._execute_image_search(
                    user=user,
                    chat_id=chat_id,
                    files=merged_agent_message.files,
                    collections=final_collections or [],
                )
                top_chunk = image_search_results[0] if image_search_results else None
                if not top_chunk or not self._is_confirmed_image_search_hit(top_chunk):
                    logger.info(
                        "Image search did not find a confirmed hit: score=%s threshold=%s",
                        top_chunk.score if top_chunk else None,
                        settings.dingtalk_image_search_confirmed_similarity,
                    )
                    unmatched_response = self._build_unmatched_image_response(agent_message.language)
                    await message_queue.put(format_stream_content(message_id, unmatched_response))
                    await message_queue.put(format_stream_end(message_id, references=[], urls=[]))
                    return {
                        "query": original_user_query,
                        "content": unmatched_response,
                        "references": [],
                    }

                chunk_text = (top_chunk.text or "").strip()
                faq_title = self._extract_faq_title(top_chunk.metadata, chunk_text)
                if not faq_title:
                    unmatched_response = self._build_unmatched_image_response(agent_message.language)
                    await message_queue.put(format_stream_content(message_id, unmatched_response))
                    await message_queue.put(format_stream_end(message_id, references=[], urls=[]))
                    return {
                        "query": original_user_query,
                        "content": unmatched_response,
                        "references": [],
                    }

                llm_agent_message = merged_agent_message.model_copy(
                    update={"query": self._build_image_search_text_query(original_user_query, faq_title, agent_message.language)}
                )

            comprehensive_prompt = build_agent_query_prompt(
                chat_id, agent_message=llm_agent_message, user=user, template=resolved_query_prompt, is_search_confirmed=False
            )
            if is_expert_expansion_confirmed:
                comprehensive_prompt = self._build_expert_expansion_prompt(agent_message.query)

            request_params = RequestParams(
                maxTokens=8192,
                model=final_completion.model,
                use_history=True,
                max_iterations=10,
                parallel_tool_calls=True,
                temperature=0.7,
                user=user,
            )
            response = await llm.generate_str(comprehensive_prompt, request_params)
            full_content = response if response else "No response generated"
            faq_choice = self._extract_faq_choice(full_content)
            if faq_choice:
                full_content = faq_choice["content"]

            await asyncio.sleep(0.1)  # Allow time for the message to be processed in listener

            await message_queue.put(format_stream_content(message_id, full_content))

            tool_references = extract_tool_call_references(llm.history)

            urls = []

            if faq_choice:
                await message_queue.put(self._format_faq_choice_message(message_id, faq_choice["label"]))

            await message_queue.put(format_stream_end(message_id, references=tool_references, urls=urls))

            return {
                "query": original_user_query,
                "content": full_content,
                "references": tool_references,
            }

        finally:
            await message_queue.close()

    def _format_exception_to_error_response(self, exception: Exception, language: str) -> AgentErrorResponse:
        """
        Convert exception to properly formatted error response using unified error handling.

        Args:
            exception: The exception to format
            language: Language code for i18n error messages

        Returns:
            Formatted error response for WebSocket
        """
        # Use existing exception hierarchy and formatting utilities
        if isinstance(exception, AgentConfigurationError):
            # Check for specific configuration error types
            error_msg = str(exception).lower()
            if "model" in error_msg or "completion" in error_msg:
                return format_invalid_model_spec_error(str(exception), language)
            else:
                return format_agent_setup_error(str(exception), language)

        elif isinstance(exception, MCPConnectionError):
            return format_mcp_connection_error(language)

        elif isinstance(exception, MCPAppInitializationError):
            return format_agent_setup_error(str(exception), language)

        else:
            # Handle unexpected errors with generic processing error
            return format_processing_error(str(exception), language)

    def _should_search_knowledge_base(
        self, query: str, files: Optional[List[view_models.File]], memory
    ) -> Optional[str]:
        """Decide whether to route user message to knowledge base search.

        Returns trigger reason string or None for free conversation.
        """
        if not query:
            return None

        if self._has_image_files(files):
            logger.info("KB search triggered: image upload")
            return "image"

        if query in {"是，专业扩展", "faq_expand"}:
            logger.info("KB search triggered: structured FAQ expansion action")
            return "expansion"

        if query in {"否，结束", "faq_end"}:
            logger.info("KB search skipped: structured FAQ end action")
            return "faq_end"

        if self._detect_expert_expansion_confirmation(query, memory):
            logger.info("KB search triggered: expansion confirmation")
            return "expansion"

        normalized = re.sub(r"[\s!！?？。,.，；;:：~～]+", "", query).lower()

        if self._is_non_local_knowledge_base_query(normalized):
            logger.info("KB search skipped: non-local knowledge-base question '%s'", query)
            return None

        if self._is_knowledge_base_existence_query(normalized):
            logger.info("KB search triggered: knowledge-base existence question '%s'", query)
            return "kb_existence"

        search_triggers = {
            "查一下", "查查", "帮我查", "帮我搜", "搜一下", "搜索", "检索",
            "从知识库查", "知识库查", "查知识库", "搜知识库", "问知识库",
            "知识库", "本地库", "本地知识库",
            "search", "lookup", "find", "check", "querykb",
        }
        if any(trigger in normalized for trigger in search_triggers):
            logger.info("KB search triggered: explicit search request '%s'", query)
            return "explicit"

        return None

    def _is_knowledge_base_existence_query(self, normalized_query: str) -> bool:
        if not normalized_query:
            return False

        kb_terms = {"知识库", "本地知识库", "本地库", "库里", "库中"}
        if not any(term in normalized_query for term in kb_terms):
            return False

        existence_terms = {
            "有没有", "是否有", "有无", "是否存在", "是否收录", "收录了",
            "有相关", "相关资料", "相关文档", "包含", "有哪些",
        }
        return any(term in normalized_query for term in existence_terms)

    def _is_non_local_knowledge_base_query(self, normalized_query: str) -> bool:
        if not normalized_query:
            return False

        non_local_kb_terms = {
            "外部知识库", "官方知识库", "sap官方", "你的知识库",
            "公共知识库", "公开知识库", "网上知识库", "外部库", "官方库",
        }
        return any(term in normalized_query for term in non_local_kb_terms)

    def _build_knowledge_base_existence_query(self, original_query: str) -> str:
        return (
            "用户正在询问当前绑定的本地知识库是否包含相关资料。\n"
            "请先从对话历史识别用户实际询问的资料主题；如果当前问题只是纠正句或追问句，"
            "例如“我问的是知识库中有没有”，请使用上一轮相关主题作为检索关键词。\n"
            "请调用 search_collection 搜索所有可用的绑定知识库，然后基于检索结果回答。\n"
            "回答要求：\n"
            "1. 如果检索结果能证明存在相关资料，说明找到的知识库、文档或 FAQ 标题，并概括命中内容。\n"
            "2. 如果检索结果只能证明有相近资料，说明是相近资料，并标明差异。\n"
            "3. 如果检索到 ABAP 自测规范、ABAP 开发检查项、ABAP 开发相关文档，应回答知识库有相关 ABAP 开发规范资料，"
            "并说明资料名称和覆盖范围；不要因为资料不是 SAP 官方开发规范就回答没有相关内容。\n"
            "4. 只有 search_collection 没有返回相关或相近结果时，才回答当前知识库未检索到明确资料。\n"
            "5. 不要编造 FAQ 编号、文档名、审计信息或来源。\n\n"
            f"用户原问题：{original_query}"
        )

    def _build_short_direct_response(self, query: str, language: Optional[str]) -> Optional[str]:
        """Return a direct response for short greetings and thanks."""
        if not query:
            return None

        normalized = re.sub(r"[\s!！?？。,.，；;:：~～]+", "", query).lower()
        if not normalized or len(normalized) > 24:
            return None

        business_markers = {
            "sap",
            "faq",
            "报错",
            "错误",
            "流程",
            "账号",
            "帐号",
            "锁定",
            "截图",
            "凭证",
            "订单",
            "发票",
            "付款",
        }
        if any(marker in normalized for marker in business_markers):
            return None

        chinese_greetings = {
            "你好",
            "您好",
            "早上好",
            "上午好",
            "中午好",
            "下午好",
            "晚上好",
            "早安",
            "晚安",
        }
        chinese_thanks = {
            "谢谢", "多谢", "感谢", "谢谢你", "谢谢啦", "多谢了", "辛苦了",
            "好的谢谢", "好的感谢", "好谢谢", "好的多谢",
        }
        english_greetings = {"hi", "hello", "hey", "goodmorning", "goodafternoon", "goodevening"}
        english_thanks = {"thanks", "thankyou", "thx", "ty", "okthanks", "okaythanks", "greatthanks"}

        if normalized in chinese_greetings:
            return (
                "你好！我是 SAPilot 运维FAQ问答助手，可以帮你查询 SAP 人财物运维常见问题、解释报错原因，"
                "并给出现场处理建议。你可以直接描述问题，或上传报错截图。"
            )
        if normalized in chinese_thanks or any(word in normalized for word in chinese_thanks):
            return "不客气！你可以继续描述 SAP 运维问题，或上传报错截图，我会继续帮你分析。"
        if normalized in english_greetings:
            return (
                "Hello! I am the SAPilot Operations FAQ Assistant. I can help you look up SAP support FAQs, "
                "explain errors, and suggest on-site troubleshooting steps. You can describe the issue or upload an error screenshot."
            )
        if normalized in english_thanks or any(word in normalized for word in english_thanks):
            return "You're welcome. You can continue describing the SAP support issue or upload an error screenshot for analysis."

        if language == "zh-CN" and normalized in {"好", "嗯", "行"}:
            return "好的，你可以继续描述 SAP 运维问题，或上传报错截图，我会帮你分析。"

        return None

    def _build_image_search_text_query(self, original_query: str, faq_title: str, language: Optional[str] = None) -> str:
        language_rule = (
            "回答语言规则：中文问中文回答，英文问英文回答，"
            f"其他语言问则用Agent默认语言（{language or 'en-US'}）回答。\n"
        )
        return (
            f"{language_rule}"
            "用户上传的截图疑似对应以下FAQ标题。请把该标题作为检索关键词，"
            "继续调用 search_collection 检索运维FAQ知识库，再按检索结果回答。\n"
            f"检索关键词：{faq_title}\n\n"
            f"用户原始问题：{original_query}"
        )

    def _extract_faq_choice(self, content: str) -> Optional[Dict[str, str]]:
        marker = "是否需要我从专业角度扩展解答？"
        if marker not in content:
            return None
        return {
            "content": content,
            "label": marker,
        }

    def _format_faq_choice_message(self, message_id: str, label: str) -> Dict[str, Any]:
        return {
            "type": "faq_choice",
            "id": message_id,
            "data": label,
            "timestamp": int(time.time()),
            "options": [
                {"label": "是，专业扩展", "action": "faq_expand"},
                {"label": "否，结束", "action": "faq_end"},
            ],
        }

    def _build_faq_choice_end_response(self, language: Optional[str]) -> str:
        if language == "zh-CN":
            return "好的，本次基于知识库标准答案的解答已结束。"
        return "OK. This FAQ answer is complete."

    def _build_unmatched_image_response(self, language: Optional[str]) -> str:
        if language == "zh-CN":
            return "未匹配到知识库中的明确图片，请用文字描述问题或补充报错文本，我再帮你查询。"
        return "I could not find a clear matching image in the knowledge base. Please describe the issue in text or provide the error message, and I will search again."

    def _should_continue_unmatched_image_prompt(self, query: str, history: List[StoredChatMessage]) -> bool:
        if not self._is_short_follow_up_query(query):
            return False
        last_assistant = self._get_last_assistant_history_message(history)
        if not last_assistant:
            return False
        return self._is_unmatched_image_response(last_assistant.content or "")

    def _is_short_follow_up_query(self, query: str) -> bool:
        normalized = re.sub(r"[\s!！?？。,.，；;:：~～]+", "", query or "").lower()
        return normalized in {
            "怎么办",
            "怎么处理",
            "如何处理",
            "怎么解决",
            "如何解决",
            "咋办",
            "然后呢",
            "下一步",
            "继续",
            "处理办法",
            "解决办法",
            "whatnow",
            "howtofix",
            "howtosolve",
        }

    def _get_last_assistant_history_message(self, history: List[StoredChatMessage]) -> Optional[StoredChatMessage]:
        for message in reversed(history or []):
            if message.role == "assistant":
                return message
        return None

    def _is_unmatched_image_response(self, content: str) -> bool:
        return (
            "未匹配到知识库中的明确图片" in content
            or "could not find a clear matching image" in content.lower()
        )

    def _has_image_files(self, files: Optional[List[view_models.File]]) -> bool:
        if not files:
            return False
        return any(self._is_image_file(file) for file in files)

    def _is_image_file(self, file: view_models.File) -> bool:
        name = (getattr(file, "name", None) or "").lower()
        return name.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"))

    def _is_confirmed_image_search_hit(self, result: DocumentWithScore) -> bool:
        score = result.score if result else None
        return isinstance(score, (int, float)) and score >= settings.dingtalk_image_search_confirmed_similarity

    def _extract_faq_title(self, metadata: Optional[dict], chunk_text: str) -> str:
        """Extract FAQ title from metadata first, then fallback to parsing chunk text."""
        if metadata and metadata.get("faq_title"):
            return metadata["faq_title"].strip()

        return self._extract_faq_question_text(chunk_text)

    def _extract_faq_question_text(self, chunk_text: str) -> str:
        if not chunk_text:
            return ""

        table_rows = [
            [cell.strip() for cell in line.strip().strip("|").split("|")]
            for line in chunk_text.splitlines()
            if "|" in line
        ]
        def is_separator_row(cells: List[str]) -> bool:
            return all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells if cell)

        for row_index, cells in enumerate(table_rows):
            if len(cells) < 2 or is_separator_row(cells):
                continue
            for index, cell in enumerate(cells[:-1]):
                if "问题描述" in cell:
                    inline_match = re.search(r"问题描述\s*[:：]\s*(.+)", cell)
                    if inline_match:
                        return inline_match.group(1).strip()
                    for next_row in table_rows[row_index + 1 :]:
                        if is_separator_row(next_row):
                            continue
                        if len(next_row) > index and next_row[index]:
                            return next_row[index].strip()
                    for next_cell in cells[index + 1 :]:
                        if next_cell:
                            return next_cell.strip()

        match = re.search(r"问题描述\s*[:：]\s*([^|\n]+)", chunk_text)
        if match:
            return match.group(1).strip()

        return ""

    async def _execute_image_search(
        self,
        user: str,
        chat_id: str,
        files: List[view_models.File],
        collections: List[view_models.Collection],
    ) -> List[DocumentWithScore]:
        """Execute image search and return enriched results with FAQ chunks."""
        from aperag.config import settings

        if not files or not collections:
            return []

        top_k = settings.dingtalk_image_search_topk
        similarity_threshold = settings.dingtalk_image_search_similarity
        contexts: List[DocumentWithScore] = []

        for file in files:
            try:
                data_uri = await image_search_service._load_chat_image_as_data_uri(user, chat_id, file.id)
                if not data_uri:
                    continue
                results = await image_search_service.search_similar_images(
                    user_id=user,
                    collections=collections,
                    image_data_uri=data_uri,
                    top_k=top_k,
                    similarity_threshold=similarity_threshold,
                )
                contexts.extend(results)
            except Exception:
                logger.exception("Failed to execute image search for file=%s", file.id)

        if not contexts:
            return []

        # Enrich with FAQ chunks to get proper text content
        return await image_search_service._enrich_results_with_faq_chunks(user, contexts)

    def _build_image_search_standard_references(
        self,
        image_search_results: List[DocumentWithScore],
    ) -> List[Dict[str, Any]]:
        """Build standard-format references from image search results, matching text search reference format."""
        if not image_search_results:
            return []

        # Take the first (best) result as the main reference
        main_result = image_search_results[0]
        metadata = main_result.metadata or {}

        # Build reference metadata matching _format_search_reference output
        reference_metadata = {
            **metadata,
            "type": "search_collection",
            "collection_id": metadata.get("collection_id"),
            "document_id": metadata.get("document_id"),
            "asset_id": metadata.get("asset_id"),
            "recall_type": "vision_search",
            "chunk_type": metadata.get("chunk_type", "faq_entry"),
            "faq_id": metadata.get("faq_id"),
            "document_source": metadata.get("source"),
            "rank": 1,
            "result_count": len(image_search_results),
        }

        # Use enriched text content from FAQ chunk
        text_content = main_result.text or ""

        return [{
            "text": text_content,
            "metadata": reference_metadata,
            "score": main_result.score or 1.0,
        }]

    async def _build_image_search_references(
        self,
        user_id: str,
        files: Optional[List[view_models.File]],
        collections: List[view_models.Collection],
    ) -> List[Dict[str, Any]]:
        """Build references from image search results for chat messages"""
        if not files or not collections:
            return []
        
        try:
            # Get the actual search results (not just formatted context)
            top_k = settings.dingtalk_image_search_topk
            similarity_threshold = settings.dingtalk_image_search_similarity
            contexts: List[DocumentWithScore] = []
            
            for file in files:
                data_uri = await image_search_service._load_chat_image_as_data_uri(user_id, "", file.id)
                if not data_uri:
                    continue
                results = await image_search_service.search_similar_images(
                    user_id=user_id,
                    collections=collections,
                    image_data_uri=data_uri,
                    top_k=top_k,
                    similarity_threshold=similarity_threshold,
                )
                contexts.extend(results)
            
            if not contexts:
                return []
            
            # Enrich with FAQ chunks to get proper text content
            enriched_results = await image_search_service._enrich_results_with_faq_chunks(user_id, contexts)
            if not enriched_results:
                return []
            
            # Take the first result as the main reference
            main_result = enriched_results[0]
            metadata = main_result.metadata or {}
            
            # Build reference metadata
            reference_metadata = {
                **metadata,
                "type": "image_search",
                "recall_type": "vision_search",
                "collection_id": metadata.get("collection_id"),
                "document_id": metadata.get("document_id"),
                "asset_id": metadata.get("asset_id"),
                "faq_id": metadata.get("faq_id"),
                "score": main_result.score or 1.0,
                # Ensure FAQ entry detection works
                "chunk_type": "faq_entry",
            }
            
            # Use the enriched text content
            text_content = main_result.text or ""
            if not text_content:
                # Fallback to basic info if no text content
                faq_id = metadata.get("faq_id", "未知FAQ")
                collection_title = metadata.get("collection_title", "未知知识库")
                text_content = f"图片搜索匹配到 FAQ: {faq_id} (知识库: {collection_title})"
            
            return [{
                "text": text_content,
                "metadata": reference_metadata,
                "score": main_result.score or 1.0,
            }]
            
        except Exception as e:
            logger.exception("Failed to build image search references: %s", e)
            return []

    async def chat_for_evaluation(
        self,
        query: str,
        user_id: str,
        model_name: str,
        model_service_provider: str,
        custom_llm_provider: Optional[Dict],
        collections: List[view_models.Collection],
        language: str = "en-US",
    ) -> StoredChatMessage | AgentErrorResponse:
        """
        Handle internal chat requests for evaluation tasks, bypassing WebSockets.
        Returns the AI response as a dictionary representation of StoredChatMessage.
        """
        # Construct AgentMessage
        agent_message = view_models.AgentMessage(
            query=query,
            completion=view_models.ModelSpec(
                model=model_name,
                model_service_provider=model_service_provider,
                custom_llm_provider=custom_llm_provider,
            ),
            collections=collections,
            language=language,
        )

        # Generate unique IDs for this interaction
        chat_id = f"eval-chat-{uuid.uuid4()}"
        message_id = str(uuid.uuid4())
        trace_id = None

        try:
            message_queue = AgentMessageQueue()
            trace_id = await self.register_message_queue(agent_message.language, chat_id, message_id, message_queue)

            # Simplified consumer that just collects results without a websocket
            async def consume_and_collect():
                tool_calls = []
                while True:
                    message = await message_queue.get()
                    if message is None:
                        break
                    if isinstance(message, dict) and message.get("type") == "tool_call_result":
                        tool_calls.append(message)
                return tool_calls

            process_task = asyncio.create_task(
                self.process_agent_message(
                    agent_message,
                    user_id,
                    chat_id,
                    message_id,
                    message_queue,
                )
            )
            consumer_task = asyncio.create_task(consume_and_collect())

            process_result, consumer_result = await asyncio.gather(process_task, consumer_task, return_exceptions=True)

            # Handle process_task exceptions with unified error formatting
            if isinstance(process_result, Exception):
                logger.error(f"Process task failed: {process_result}")
                error_response = self._format_exception_to_error_response(
                    process_result, agent_message.language or "en-US"
                )
                return error_response

            # Handle consumer_task exceptions
            if isinstance(consumer_result, Exception):
                logger.error(f"Consumer task failed: {consumer_result}")
                error_response = format_processing_error(str(consumer_result), agent_message.language or "en-US")
                return error_response

            query = process_result.get("query", "")
            ai_response = process_result.get("content", "")
            references = process_result.get("references", "")
            tool_use_list = consumer_result

            # AI message
            ai_message = create_assistant_message(
                content=ai_response,
                chat_id=chat_id,
                message_id=message_id,
                trace_id=trace_id,
                tool_use_list=tool_use_list,
                references=references,
                # urls=,
            )
            return ai_message

        except Exception as e:
            logger.error(f"Error during internal agent chat for evaluation: {e}")
            error_response = self._format_exception_to_error_response(e, agent_message.language or "en-US")
            return error_response
        finally:
            if trace_id:
                await agent_event_listener.unregister_listener(str(trace_id))

    async def _save_conversation_history(
        self,
        chat_id: str,
        message_id: str,
        trace_id: str,
        query: str,
        ai_response: str,
        files: List[Dict[str, Any]],
        tool_use_list: List[Dict],
        tool_references: List[Dict[str, Any]],
    ) -> None:
        """
        Save conversation history from successful agent processing.

        Args:
            chat_id: Chat session ID
            conversation_data: Dictionary containing query, content, and references
        """
        try:
            # Get history instance through history manager
            history = await self.history_manager.get_chat_history(chat_id)

            # Save conversation turn with data from successful processing
            history_saved = await self.history_manager.save_conversation_turn(
                message_id=message_id,
                trace_id=trace_id,
                history=history,
                user_query=query,
                ai_response=ai_response,
                files=files,
                tool_use_list=tool_use_list,
                tool_references=tool_references,
            )

            if not history_saved:
                logger.warning(f"Failed to save conversation history for chat: {chat_id}")

        except Exception as e:
            # Don't let history saving errors break the flow
            logger.error(f"Error saving conversation history for chat {chat_id}: {e}")

    def _detect_search_confirmation(self, current_query: str, memory) -> bool:
        """
        Detect if user is confirming web search from a previous turn.
        
        Returns True if:
        1. Last AI message contains search prompt ("是否需要启动联网搜索")
        2. Current user message is a confirmation word
        """
        if not current_query or not memory:
            logger.info("_detect_search_confirmation: No query or memory, returning False")
            return False
            
        # Check if last AI message asked about search
        # memory.history is a list of messages in OpenAI format
        last_ai_msg = None
        if hasattr(memory, 'history') and memory.history:
            for msg in reversed(memory.history):
                # Messages can be dicts with 'role' key
                if isinstance(msg, dict) and msg.get('role') == 'assistant':
                    last_ai_msg = msg
                    break
                # Or objects with 'role' attribute
                elif hasattr(msg, 'role') and msg.role == 'assistant':
                    last_ai_msg = msg
                    break
        
        if not last_ai_msg:
            logger.info("_detect_search_confirmation: No last AI message found in memory.history, returning False")
            return False
            
        # Check if AI asked about web search
        if isinstance(last_ai_msg, dict):
            last_ai_content = last_ai_msg.get('content', '') or ''
        else:
            last_ai_content = getattr(last_ai_msg, 'content', '') or ''
            
        logger.info(f"_detect_search_confirmation: Last AI content (first 300): {last_ai_content[:300]}")
        
        if '是否需要启动联网搜索' not in last_ai_content and '是否需要搜索' not in last_ai_content:
            logger.info("_detect_search_confirmation: Last AI message did not ask about search, returning False")
            return False
            
        # Check if user's current message is a confirmation
        confirmation_words = {'可以', '好', '是', '对', 'ok', '行', '嗯', '要的', '需要', '联网搜索', '搜索', '搜一下', '帮我搜', '请搜索', 'yes', 'sure'}
        query_lower = current_query.lower().strip()
        logger.info(f"_detect_search_confirmation: Current query: '{query_lower}'")
        
        # Direct match or contains any confirmation word
        if query_lower in confirmation_words:
            logger.info("_detect_search_confirmation: Query matches confirmation word directly, returning True")
            return True
        for word in confirmation_words:
            if word in query_lower:
                logger.info(f"_detect_search_confirmation: Query contains confirmation word '{word}', returning True")
                return True
                
        logger.info("_detect_search_confirmation: No confirmation found, returning False")
        return False

    def _detect_expert_expansion_confirmation(self, current_query: str, memory) -> bool:
        """Detect if user wants the LLM to expand a prior FAQ answer professionally."""
        if not current_query or not memory:
            return False

        last_ai_content = self._get_last_ai_content(memory)
        if "是否需要我从专业角度扩展解答" not in last_ai_content:
            return False

        if self._detect_expansion_rejection(current_query, memory):
            return False

        confirmation_words_exact = {
            "可以",
            "好的",
            "好",
            "是",
            "行",
            "嗯",
            "需要",
            "要的",
            "扩展",
            "扩展一下",
            "专业解答",
            "详细说说",
            "补充一下",
            "继续",
            "ok",
            "yes",
            "sure",
        }
        query_lower = current_query.lower().strip()

        # Only match if the query is itself a short confirmation (<=10 chars)
        # or if an exact confirmation word appears as a standalone token
        if len(query_lower) <= 10 and query_lower in confirmation_words_exact:
            return True
        tokens = set(query_lower.split())
        return any(word in tokens and word in confirmation_words_exact for word in tokens)

    def _detect_expansion_rejection(self, current_query: str, memory) -> bool:
        """Detect if user is rejecting the expansion offer from a previous FAQ turn."""
        if not current_query or not memory:
            return False

        last_ai_content = self._get_last_ai_content(memory)
        if "是否需要我从专业角度扩展解答" not in last_ai_content:
            return False

        rejection_words = {
            "不用",
            "不用了",
            "不需要",
            "不需要了",
            "不用扩展",
            "算了",
            "不了",
            "没必要",
            "no",
            "nope",
            "notneeded",
            "skip",
            "不用谢谢",
            "不了谢谢",
            "oknothanks",
        }
        query_lower = current_query.lower().strip()
        if query_lower in rejection_words:
            return True
        return any(word in query_lower for word in rejection_words)

    def _build_expansion_rejection_response(self, language: Optional[str]) -> str:
        if language == "zh-CN":
            return "好的，如有其他问题随时提问。"
        return "Sure, feel free to ask if you have other questions."

    def _get_last_ai_content(self, memory) -> str:
        """Return the most recent assistant message content from memory history."""
        if not hasattr(memory, "history") or not memory.history:
            return ""

        for msg in reversed(memory.history):
            if isinstance(msg, dict) and msg.get("role") == "assistant":
                return msg.get("content", "") or ""
            if hasattr(msg, "role") and msg.role == "assistant":
                return getattr(msg, "content", "") or ""
        return ""

    def _build_expert_expansion_prompt(self, current_query: str) -> str:
        return f"""用户确认需要专业扩展解答。

请基于上一轮 FAQ 标准回答和对话上下文，从 SAP 顾问现场支持角度补充说明。不要再次检索知识库，不要启动联网搜索，不要重复 FAQ 标准回答。
不要重新询问用户遇到了什么 SAP 报错，不要回到接待话术，不要再次询问是否需要扩展解答。

回答格式：
【专业扩展解答】
1. 现场处理建议
2. 常见风险或注意事项
3. 下一步排查方向

用户当前回复：{current_query}"""
