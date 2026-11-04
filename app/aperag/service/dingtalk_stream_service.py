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
import base64
import logging
import threading
from typing import Any, Dict, Optional

import dingtalk_stream
from dingtalk_stream import AckMessage, ChatbotHandler, DingTalkStreamClient

from aperag.config import settings
from aperag.service.dingtalk_bot_service import DingTalkBotService
from aperag.service.setting_service import setting_service

logger = logging.getLogger(__name__)


class DingTalkStreamMessage:
    """Message wrapper for thread-safe communication."""

    def __init__(self, payload: Dict[str, Any], chatbot_message: dingtalk_stream.chatbot.ChatbotMessage):
        self.payload = payload
        self.chatbot_message = chatbot_message
        self.result: Optional[str] = None
        self.error: Optional[str] = None
        self.future: Optional[asyncio.Future] = None


class _PendingAttachmentMessage:
    def __init__(self, payload: Dict[str, Any], chatbot_message: dingtalk_stream.chatbot.ChatbotMessage, flush_task: asyncio.Task):
        self.payload = payload
        self.chatbot_message = chatbot_message
        self.flush_task = flush_task


class DingTalkStreamBotHandler(ChatbotHandler):
    """Handle DingTalk Stream mode bot messages."""

    def __init__(self, message_queue: asyncio.Queue, result_queue: asyncio.Queue, dingtalk_bot_service=None):
        super().__init__()
        self.message_queue = message_queue
        self.result_queue = result_queue
        self._dingtalk_bot_service = dingtalk_bot_service
        self._pending_attachment_messages: Dict[str, _PendingAttachmentMessage] = {}
        self._pending_lock = asyncio.Lock()
        self._attachment_merge_window_seconds = 3.0

    async def process(self, message: dingtalk_stream.frames.CallbackMessage):
        """Process incoming bot message."""
        try:
            chatbot_message = dingtalk_stream.chatbot.ChatbotMessage.from_dict(message.data)

            text_list = self.extract_text_from_incoming_message(chatbot_message)
            text_content = "\n".join(text_list) if text_list else ""
            raw_content = message.data.get("content") if isinstance(message.data.get("content"), dict) else None
            # Keep raw DingTalk downloadCode values. The SDK helper downloads and
            # re-uploads images, which hides whether Stream delivered the image.
            image_list = chatbot_message.get_image_list() or []

            logger.info(
                "DingTalk Stream: incoming message msg_id=%s type=%s text_count=%s image_count=%s content_keys=%s",
                chatbot_message.message_id,
                chatbot_message.message_type,
                len(text_list or []),
                len(image_list),
                sorted((message.data.get("content") or {}).keys()) if isinstance(message.data.get("content"), dict) else [],
            )

            if image_list:
                logger.info(
                    "DingTalk Stream: received image message type=%s count=%s refs=%s",
                    chatbot_message.message_type,
                    len(image_list),
                    [str(code)[:30] for code in image_list],
                )

            if not text_content.strip():
                if image_list:
                    text_content = "用户上传了报错截图，请结合图片信息分析。"
                elif self._is_file_message(chatbot_message.message_type, raw_content):
                    text_content = ""
                else:
                    return AckMessage.STATUS_OK, "OK"

            downloaded_image_data = []
            if image_list:
                for download_code in image_list[:3]:
                    try:
                        download_url = self.get_image_download_url(download_code)
                        if download_url:
                            import requests as sync_requests
                            img_resp = sync_requests.get(download_url, timeout=30)
                            if img_resp.status_code == 200:
                                content_type = img_resp.headers.get("content-type", "image/png").split(";")[0].strip()
                                b64 = base64.b64encode(img_resp.content).decode("utf-8")
                                data_uri = f"data:{content_type};base64,{b64}"
                                downloaded_image_data.append(data_uri)
                                logger.info("DingTalk Stream: downloaded image %s bytes=%s", download_code[:30], len(img_resp.content))
                    except Exception:
                        logger.exception("DingTalk Stream: failed to download image downloadCode=%s", download_code[:30])

            payload = self._build_payload(chatbot_message, text_content, image_list, raw_content)

            if downloaded_image_data:
                payload["image_data_uris"] = downloaded_image_data

            if self._should_buffer_attachment_message(payload, text_content):
                await self._buffer_attachment_message(payload, chatbot_message)
                return AckMessage.STATUS_OK, "OK"

            merged = await self._merge_with_pending_attachment_message(payload, chatbot_message, text_content)
            if merged is not None:
                payload = merged

            await self._dispatch_message(payload, chatbot_message)
            return AckMessage.STATUS_OK, "OK"

        except Exception as e:
            logger.exception("Failed to process DingTalk Stream message")
            return AckMessage.STATUS_SYSTEM_EXCEPTION, str(e)

    def _build_payload(self, chatbot_message: dingtalk_stream.chatbot.ChatbotMessage,
                       text_content: str, image_list: list, raw_content: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Build payload compatible with existing handler."""
        payload = {
            "msgtype": chatbot_message.message_type or "text",
            "text": {"content": text_content},
            "senderStaffId": chatbot_message.sender_staff_id,
            "senderId": chatbot_message.sender_id,
            "conversationId": chatbot_message.conversation_id,
            "chatid": chatbot_message.conversation_id,
            "robotCode": chatbot_message.robot_code,
            "chatbotUserId": chatbot_message.chatbot_user_id,
            "sessionWebhook": chatbot_message.session_webhook,
            "session_webhook": chatbot_message.session_webhook,
            "createAt": chatbot_message.create_at,
            "isAdmin": chatbot_message.is_admin,
        }

        if raw_content:
            payload["content"] = raw_content

        if chatbot_message.rich_text_content and chatbot_message.rich_text_content.rich_text_list:
            payload["richText"] = chatbot_message.rich_text_content.rich_text_list

        if image_list:
            payload["image"] = {"downloadCode": image_list[0]}

        return payload

    async def _dispatch_message(
        self,
        payload: Dict[str, Any],
        chatbot_message: dingtalk_stream.chatbot.ChatbotMessage,
    ) -> None:
        self.reply_text("SAPilot：收到，思考中...", chatbot_message)

        stream_message = DingTalkStreamMessage(payload, chatbot_message)
        stream_message.future = asyncio.get_running_loop().create_future()
        await self.message_queue.put(stream_message)

        try:
            result_message = await asyncio.wait_for(stream_message.future, timeout=300.0)
            if result_message.error:
                self.reply_text(f"SAPilot：处理失败，请稍后重试。错误：{result_message.error}", chatbot_message)
            elif result_message.result:
                self.reply_markdown("SAPilot 现场问诊", result_message.result, chatbot_message)
        except asyncio.TimeoutError:
            self.reply_text("SAPilot：处理超时，请稍后重试。", chatbot_message)

    def _pending_key(self, chatbot_message: dingtalk_stream.chatbot.ChatbotMessage) -> str:
        return f"{chatbot_message.conversation_id}:{chatbot_message.sender_staff_id or chatbot_message.sender_id or ''}"

    def _should_buffer_attachment_message(self, payload: Dict[str, Any], text_content: str) -> bool:
        normalized_text = (text_content or "").strip()
        return bool(self._has_file_attachments(payload) and not normalized_text)

    async def _buffer_attachment_message(
        self,
        payload: Dict[str, Any],
        chatbot_message: dingtalk_stream.chatbot.ChatbotMessage,
    ) -> None:
        key = self._pending_key(chatbot_message)
        flush_task = asyncio.create_task(self._flush_pending_attachment_message_after_delay(key))
        pending = _PendingAttachmentMessage(payload, chatbot_message, flush_task)

        async with self._pending_lock:
            previous = self._pending_attachment_messages.get(key)
            if previous:
                previous.flush_task.cancel()
                pending.payload = self._merge_payloads(previous.payload, payload)
            self._pending_attachment_messages[key] = pending

        logger.info("Buffered DingTalk attachment-only message key=%s", key)

    async def _merge_with_pending_attachment_message(
        self,
        payload: Dict[str, Any],
        chatbot_message: dingtalk_stream.chatbot.ChatbotMessage,
        text_content: str,
    ) -> Optional[Dict[str, Any]]:
        if not (text_content or "").strip():
            return None

        key = self._pending_key(chatbot_message)
        async with self._pending_lock:
            pending = self._pending_attachment_messages.pop(key, None)

        if not pending:
            return None

        pending.flush_task.cancel()
        merged_payload = self._merge_payloads(pending.payload, payload)
        logger.info("Merged DingTalk attachment message with following text key=%s", key)
        return merged_payload

    async def _flush_pending_attachment_message_after_delay(self, key: str) -> None:
        try:
            await asyncio.sleep(self._attachment_merge_window_seconds)
            async with self._pending_lock:
                pending = self._pending_attachment_messages.pop(key, None)
            if not pending:
                return

            logger.info("Flushing buffered DingTalk attachment-only message key=%s", key)
            await self._dispatch_message(pending.payload, pending.chatbot_message)
        except asyncio.CancelledError:
            return
        except Exception:
            logger.exception("Failed to flush buffered DingTalk attachment-only message key=%s", key)

    def _merge_payloads(self, base_payload: Dict[str, Any], override_payload: Dict[str, Any]) -> Dict[str, Any]:
        merged = dict(base_payload)
        merged.update(override_payload)

        base_text = ((base_payload.get("text") or {}).get("content") or "").strip()
        override_text = ((override_payload.get("text") or {}).get("content") or "").strip()
        if override_text:
            merged["text"] = {"content": override_text}
        elif base_text:
            merged["text"] = {"content": base_text}

        merged_rich_text = self._merge_lists(base_payload.get("richText"), override_payload.get("richText"))
        if merged_rich_text:
            merged["richText"] = merged_rich_text

        merged_image_data = self._merge_lists(base_payload.get("image_data_uris"), override_payload.get("image_data_uris"))
        if merged_image_data:
            merged["image_data_uris"] = merged_image_data

        if base_payload.get("image") and not override_payload.get("image"):
            merged["image"] = base_payload["image"]
        return merged

    def _merge_lists(self, base_value: Any, override_value: Any) -> list[Any]:
        merged: list[Any] = []
        for value in (base_value, override_value):
            if isinstance(value, list):
                merged.extend(value)
        return merged

    def _has_file_attachments(self, payload: Dict[str, Any]) -> bool:
        msgtype = str(payload.get("msgtype") or payload.get("msgType") or payload.get("messageType") or "").strip().lower()
        content = payload.get("content")
        if isinstance(content, dict) and self._contains_download_code(content):
            if msgtype == "file" or content.get("fileName"):
                return True
            content_type = str(content.get("type") or content.get("msgType") or content.get("tag") or "").strip().lower()
            if content_type and any(keyword in content_type for keyword in ("file", "attachment", "doc", "link")):
                return True
        if isinstance(content, dict) and msgtype == "file":
            return True

        rich_text = payload.get("richText")
        if not isinstance(rich_text, list):
            return False

        for item in rich_text:
            if self._is_non_image_attachment_item(item):
                return True
        return False

    def _is_non_image_attachment_item(self, item: Any) -> bool:
        if not isinstance(item, dict):
            return False

        item_type = str(item.get("type") or item.get("msgType") or item.get("tag") or "").strip().lower()
        if item_type and any(keyword in item_type for keyword in ("image", "picture", "photo")):
            return False

        if self._contains_download_code(item):
            return True

        for key in ("file", "attachment", "content", "extra", "value", "data"):
            nested = item.get(key)
            if isinstance(nested, dict) and self._contains_download_code(nested):
                return True
        return False

    def _contains_download_code(self, value: Dict[str, Any]) -> bool:
        return any(value.get(key) for key in ("downloadCode", "download_code", "mediaId", "media_id"))

    def _is_file_message(self, message_type: Optional[str], raw_content: Optional[Dict[str, Any]]) -> bool:
        normalized_type = str(message_type or "").strip().lower()
        if normalized_type == "file":
            return True
        if not isinstance(raw_content, dict):
            return False
        return bool(raw_content.get("fileName") and self._contains_download_code(raw_content))


class DingTalkStreamConsumer:
    """DingTalk Stream mode consumer service."""

    def __init__(self):
        self.client: Optional[DingTalkStreamClient] = None
        self.handler: Optional[DingTalkStreamBotHandler] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self.message_queue: Optional[asyncio.Queue] = None
        self.result_queue: Optional[asyncio.Queue] = None
        self._main_loop: Optional[asyncio.AbstractEventLoop] = None
        self._dingtalk_bot_service: Optional[DingTalkBotService] = None

    async def start(self):
        """Start the Stream consumer."""
        self._main_loop = asyncio.get_running_loop()

        self.message_queue = asyncio.Queue()
        self.result_queue = asyncio.Queue()

        self._dingtalk_bot_service = DingTalkBotService()

        db_settings = await setting_service.get_all_settings()

        client_id = db_settings.get("dingtalk_app_key", settings.dingtalk_app_key)
        client_secret = db_settings.get("dingtalk_app_secret", settings.dingtalk_app_secret)

        if not client_id or not client_secret:
            logger.warning("DingTalk Stream mode not started: missing Client ID or Client Secret")
            return

        enabled = db_settings.get("dingtalk_enabled", settings.dingtalk_enabled)
        if not enabled:
            logger.info("DingTalk Stream mode not started: disabled")
            return

        try:
            credential = dingtalk_stream.Credential(client_id, client_secret)
            self.client = DingTalkStreamClient(credential)
            self.handler = DingTalkStreamBotHandler(self.message_queue, self.result_queue, self._dingtalk_bot_service)
            self.client.register_callback_handler(
                dingtalk_stream.chatbot.ChatbotMessage.TOPIC,
                self.handler
            )

            logger.info("Starting DingTalk Stream consumer with Client ID: %s", client_id)

            asyncio.create_task(self._process_messages())

            self._running = True
            self._thread = threading.Thread(target=self._run_client, daemon=True)
            self._thread.start()

            logger.info("DingTalk Stream consumer started successfully")
        except Exception:
            logger.exception("Failed to start DingTalk Stream consumer")
            raise

    async def _process_messages(self):
        """Process messages from queue in main thread."""
        logger.info("Starting DingTalk Stream message processor")
        while self._running:
            try:
                stream_message = await asyncio.wait_for(
                    self.message_queue.get(),
                    timeout=1.0
                )

                try:
                    result = await self._dingtalk_bot_service.handle_callback(
                        stream_message.payload,
                        None,
                        None
                    )

                    if isinstance(result, dict):
                        if result.get("msgtype") == "text":
                            answer = result.get("text", {}).get("content", "")
                        elif result.get("msgtype") == "markdown":
                            answer = result.get("markdown", {}).get("text", "")
                        else:
                            answer = str(result)
                    else:
                        answer = str(result)

                    stream_message.result = answer
                except Exception as e:
                    logger.exception("Failed to process DingTalk message")
                    stream_message.error = str(e)

                if stream_message.future and not stream_message.future.done():
                    stream_message.future.set_result(stream_message)
                else:
                    await self.result_queue.put(stream_message)

            except asyncio.TimeoutError:
                continue
            except Exception:
                logger.exception("Error in message processor")

    def _run_client(self):
        """Run the Stream client in a separate thread."""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self.client.start_forever()
        except Exception:
            logger.exception("DingTalk Stream client error")
        finally:
            self._running = False

    async def stop(self):
        """Stop the Stream consumer."""
        self._running = False
        if self.client:
            try:
                logger.info("Stopping DingTalk Stream consumer")
            except Exception:
                logger.exception("Error stopping DingTalk Stream consumer")

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)


dingtalk_stream_consumer = DingTalkStreamConsumer()
