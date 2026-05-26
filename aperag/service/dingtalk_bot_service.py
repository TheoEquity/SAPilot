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
import hashlib
import hmac
import io
import json
import logging
import mimetypes
import os
import time
import urllib.parse
import uuid
from typing import Any, Dict, List, Optional

import httpx
from fastapi import UploadFile
from starlette.datastructures import Headers
from sqlalchemy import and_, select

from aperag.config import settings
from aperag.db import models as db_models
from aperag.db.models import DocumentStatus
from aperag.db.ops import async_db_ops
from aperag.schema import view_models
from aperag.service.agent_chat_service import AgentChatService
from aperag.service.chat_document_service import chat_document_service
from aperag.service.image_search_service import image_search_service
from aperag.service.prompt_template_service import prompt_template_service
from aperag.service.setting_service import setting_service

logger = logging.getLogger(__name__)


class DingTalkBotService:
    """Handle DingTalk bot callbacks and route them into SAPilot Agent chat."""

    def __init__(self):
        self.db_ops = async_db_ops
        self.agent_chat_service = AgentChatService()
        self._access_token: Optional[str] = None
        self._access_token_expire_at = 0.0

    async def _settings(self) -> Dict[str, Any]:
        db_settings = await setting_service.get_all_settings()
        return {
            "enabled": db_settings.get("dingtalk_enabled", settings.dingtalk_enabled),
            "webhook_secret": db_settings.get("dingtalk_webhook_secret", settings.dingtalk_webhook_secret),
            "outgoing_webhook_url": db_settings.get(
                "dingtalk_outgoing_webhook_url", settings.dingtalk_outgoing_webhook_url
            ),
            "outgoing_webhook_secret": db_settings.get(
                "dingtalk_outgoing_webhook_secret", settings.dingtalk_outgoing_webhook_secret
            ),
            "bot_user_id": db_settings.get("dingtalk_bot_user_id", settings.dingtalk_bot_user_id),
            "bot_id": db_settings.get("dingtalk_bot_id", settings.dingtalk_bot_id),
            "response_mode": db_settings.get("dingtalk_response_mode", settings.dingtalk_response_mode),
            "robot_code": db_settings.get("dingtalk_robot_code", settings.dingtalk_stream_client_id),
            "app_key": db_settings.get("dingtalk_app_key", settings.dingtalk_app_key),
            "app_secret": db_settings.get("dingtalk_app_secret", settings.dingtalk_app_secret),
            "image_search_enabled": settings.dingtalk_image_search_enabled,
            "sap_community_search_enabled": settings.dingtalk_sap_community_search_enabled,
        }

    def verify_signature(self, timestamp: Optional[str], sign: Optional[str], webhook_secret: Optional[str] = None) -> bool:
        secret = webhook_secret if webhook_secret is not None else settings.dingtalk_webhook_secret
        if not secret:
            return True
        if not timestamp or not sign:
            return False

        string_to_sign = f"{timestamp}\n{secret}".encode("utf-8")
        digest = hmac.new(secret.encode("utf-8"), string_to_sign, hashlib.sha256).digest()
        expected = urllib.parse.quote_plus(base64.b64encode(digest))
        return hmac.compare_digest(expected, sign)

    async def handle_callback(
        self, payload: Dict[str, Any], timestamp: Optional[str], sign: Optional[str]
    ) -> Dict[str, Any]:
        logger.info("Received DingTalk callback with keys: %s", sorted(payload.keys()))
        dingtalk_settings = await self._settings()
        if not dingtalk_settings["enabled"]:
            return self._text_response("SAPilot 钉钉机器人尚未启用。")
        if not self.verify_signature(timestamp, sign, dingtalk_settings["webhook_secret"]):
            return self._text_response("钉钉消息签名校验失败。")

        user_id = str(dingtalk_settings["bot_user_id"] or "").strip()
        bot_id = str(dingtalk_settings["bot_id"] or "").strip()
        if not user_id:
            return self._text_response("SAPilot 钉钉机器人未配置 DINGTALK_BOT_USER_ID。")

        bot = await self.db_ops.query_bot(user_id, bot_id) if bot_id else await self.find_default_agent_bot(user_id)
        if not bot:
            return self._text_response("SAPilot 钉钉机器人绑定的 Bot 不存在，请配置 DINGTALK_BOT_ID 或默认 Agent。")
        if bot.type != db_models.BotType.AGENT:
            return self._text_response("SAPilot 钉钉机器人需要绑定 Agent 类型 Bot。")

        bot_config = self._parse_bot_config(bot)
        supported_attachments = self._extract_file_attachments(payload)
        if len(supported_attachments) > 1:
            return self._text_response("上传附件仅支持单个代码文件，请一次只发送 1 个文件。")
        unsupported_attachments = self._extract_unsupported_file_attachments(payload)
        if unsupported_attachments:
            return self._text_response("上传附件仅为代码文本文件服务，其他类型不支持。搜图问诊请直接贴图。")
        query = self._build_query(payload)
        force_skill_id = self._resolve_forced_skill_id(payload, query, bot_config)
        if not query and not force_skill_id:
            return self._text_response("请发送 SAP 运维、开发问题、日志或报错截图。")

        logger.info("Processing DingTalk message for bot %s, chat payload peer %s", bot.id, self._peer_id(payload))

        default_collections = await self._default_collections(user_id, bot_config)
        chat = await self._get_or_create_dingtalk_chat(user_id, bot.id, payload)
        files = await self._upload_dingtalk_attachments_to_chat(chat.id, user_id, payload)
        pending_parse_files = [file for file in files if not self._is_image_file(file)]
        if pending_parse_files:
            ready, failed_files = await self._wait_for_chat_documents_ready(pending_parse_files)
            if not ready:
                failed_text = f"，失败附件：{', '.join(failed_files)}" if failed_files else ""
                return self._text_response(f"附件已收到，正在解析中，请稍后再试{failed_text}。")

        search_mode = self._should_search_kb(query, payload)
        if search_mode:
            image_context = ""
            formatted_query = self._format_dingtalk_query(query, image_context=image_context)
        else:
            formatted_query = query

        answer = await self._ask_agent(
            user_id,
            bot,
            chat.id,
            formatted_query,
            files=files,
            bot_config=bot_config,
            default_collections=default_collections,
            search_mode=search_mode,
            force_skill_id=force_skill_id,
        )
        return self._markdown_response("SAPilot 现场问诊", answer)

    async def send_markdown(self, title: str, content: str) -> Dict[str, Any]:
        return await self._send_outgoing_message(self._markdown_response(title, content))

    async def send_text(self, content: str, webhook_url: Optional[str] = None) -> Dict[str, Any]:
        return await self._send_outgoing_message(self._text_response(content), webhook_url=webhook_url)

    async def _send_outgoing_message(
        self, message: Dict[str, Any], webhook_url: Optional[str] = None
    ) -> Dict[str, Any]:
        dingtalk_settings = await self._settings()
        webhook_url = (webhook_url or dingtalk_settings["outgoing_webhook_url"] or "").strip()
        if not webhook_url:
            raise ValueError("DINGTALK_OUTGOING_WEBHOOK_URL is required to send DingTalk messages")

        url = self._signed_outgoing_url(webhook_url, dingtalk_settings["outgoing_webhook_secret"])
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=message)
            response.raise_for_status()
            result = response.json()

        if result.get("errcode") not in (None, 0):
            raise ValueError(f"DingTalk webhook returned error: {result}")
        logger.info("Sent DingTalk outgoing message successfully: %s", result)
        return result

    def _signed_outgoing_url(self, webhook_url: str, outgoing_secret: Optional[str] = None) -> str:
        secret = (outgoing_secret if outgoing_secret is not None else settings.dingtalk_outgoing_webhook_secret).strip()
        if not secret:
            return webhook_url

        timestamp = str(round(time.time() * 1000))
        string_to_sign = f"{timestamp}\n{secret}".encode("utf-8")
        digest = hmac.new(secret.encode("utf-8"), string_to_sign, hashlib.sha256).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(digest))
        separator = "&" if "?" in webhook_url else "?"
        return f"{webhook_url}{separator}timestamp={timestamp}&sign={sign}"

    async def _get_or_create_dingtalk_chat(self, user_id: str, bot_id: str, payload: Dict[str, Any]) -> db_models.Chat:
        peer_id = self._peer_id(payload)
        chat = await self.db_ops.query_chat_by_peer(user_id, db_models.ChatPeerType.DINGTALK, peer_id)
        if chat:
            return chat

        return await self.db_ops.create_chat(
            user=user_id,
            bot_id=bot_id,
            title="DingTalk Chat",
            peer_type=db_models.ChatPeerType.DINGTALK,
            peer_id=peer_id,
        )

    async def _ask_agent(
        self,
        user_id: str,
        bot: db_models.Bot,
        chat_id: str,
        query: str,
        files: Optional[List[view_models.File]] = None,
        bot_config: Optional[view_models.BotConfig] = None,
        default_collections: Optional[List[view_models.Collection]] = None,
        search_mode: bool = False,
        force_skill_id: Optional[str] = None,
    ) -> str:
        if bot_config is None:
            bot_config = self._parse_bot_config(bot)
        if default_collections is None:
            default_collections = await self._default_collections(user_id, bot_config)
        resolved_system_prompt = await prompt_template_service.resolve_agent_system_prompt(bot=bot, user_id=user_id)
        resolved_query_prompt = await prompt_template_service.resolve_agent_query_prompt(bot=bot, user_id=user_id)

        agent_message = view_models.AgentMessage(
            query=query,
            collections=[],
            completion=None,
            web_search_enabled=(await self._settings())["sap_community_search_enabled"],
            language="zh-CN",
            files=files or [],
            force_skill_id=force_skill_id,
        )

        message_id = str(uuid.uuid4())
        queue = _CollectingMessageQueue()
        trace_id = await self.agent_chat_service.register_message_queue(
            agent_message.language, chat_id, message_id, queue
        )

        try:
            document_ids = [file.id for file in agent_message.files or [] if file.id]
            associated_files = await chat_document_service.associate_documents_with_message(
                chat_id=chat_id,
                message_id=message_id,
                files=document_ids,
                user=user_id,
            )
            result = await self.agent_chat_service.process_agent_message(
                agent_message,
                user_id,
                chat_id,
                message_id,
                queue,
                associated_files=associated_files,
                bot_config=bot_config,
                default_collections=default_collections,
                resolved_system_prompt=resolved_system_prompt,
                resolved_query_prompt=resolved_query_prompt,
            )
            ai_response = result.get("content") or "未生成有效回答。"
            ai_response = self._append_faq_choice_text(ai_response, queue.messages)
            await self.agent_chat_service._save_conversation_history(
                chat_id,
                message_id,
                trace_id,
                result.get("query", query),
                ai_response,
                [],
                queue.tool_call_results,
                result.get("references", []),
            )
            return ai_response
        except Exception as e:
            logger.exception("Failed to process DingTalk agent message")
            error = self.agent_chat_service._format_exception_to_error_response(e, "zh-CN")
            return error.get("data") or str(e)
        finally:
            if trace_id:
                from aperag.agent.agent_event_listener import agent_event_listener

                await agent_event_listener.unregister_listener(str(trace_id))

    def _parse_bot_config(self, bot: db_models.Bot) -> Optional[view_models.BotConfig]:
        if not bot.config:
            return None
        try:
            return view_models.BotConfig(**json.loads(bot.config))
        except (json.JSONDecodeError, ValueError):
            return None

    def _append_faq_choice_text(self, content: str, messages: List[Dict[str, Any]]) -> str:
        faq_choice = next(
            (
                message
                for message in messages
                if isinstance(message, dict) and message.get("type") == "faq_choice"
            ),
            None,
        )
        if not faq_choice:
            return content

        options = faq_choice.get("options") or [
            {"label": "是，专业扩展"},
            {"label": "否，结束"},
        ]
        labels = [str(option.get("label") or "").strip() for option in options]
        labels = [label for label in labels if label]
        if not labels:
            return content

        if all(label in content for label in labels):
            return content

        choice_text = "\n\n请选择或直接回复：" + " / ".join(labels)
        return f"{content}{choice_text}"

    async def _default_collections(
        self, user_id: str, bot_config: Optional[view_models.BotConfig]
    ) -> List[view_models.Collection]:
        if not bot_config or not bot_config.agent or not bot_config.agent.collections:
            return []

        collection_ids = [collection.id for collection in bot_config.agent.collections if collection.id]
        db_collections = await self.db_ops.query_collections_by_ids(user_id, collection_ids)
        return await self.agent_chat_service._convert_db_collections_to_pydantic(db_collections)

    async def find_default_agent_bot(self, user_id: str) -> Optional[db_models.Bot]:
        async def _query(session):
            stmt = select(db_models.Bot).where(
                and_(
                    db_models.Bot.user == user_id,
                    db_models.Bot.type == db_models.BotType.AGENT,
                    db_models.Bot.is_default.is_(True),
                    db_models.Bot.status != db_models.BotStatus.DELETED,
                )
            )
            result = await session.execute(stmt)
            return result.scalars().first()

        return await self.db_ops._execute_query(_query)

    def _build_query(self, payload: Dict[str, Any]) -> str:
        msgtype = payload.get("msgtype") or payload.get("msgType") or payload.get("messageType")
        text = self._extract_text(payload).strip()
        image_urls = self._extract_image_urls(payload)
        file_attachments = self._extract_file_attachments(payload)

        if not text and (image_urls or file_attachments):
            return ""

        parts = []
        if text:
            parts.append(text)
        if image_urls:
            parts.append("用户上传了报错截图，请结合图片信息分析。")
            parts.extend([f"图片地址：{url}" for url in image_urls])
        if file_attachments:
            file_names = [attachment.get("file_name") for attachment in file_attachments if attachment.get("file_name")]
            if file_names:
                parts.append(f"用户上传了附件，请结合附件内容分析：{', '.join(file_names[:3])}")
            else:
                parts.append("用户上传了附件，请结合附件内容分析。")
        if not parts and msgtype:
            parts.append(f"收到钉钉 {msgtype} 类型消息，请提示用户补充 SAP 问题、日志或截图。")

        query = "\n".join(parts)
        return self._strip_bot_mentions(query)

    def _resolve_forced_skill_id(
        self,
        payload: Dict[str, Any],
        query: str,
        bot_config: Optional[view_models.BotConfig],
    ) -> Optional[str]:
        normalized_query = self._strip_bot_mentions(query or "").strip()
        has_images = bool(self._extract_image_urls(payload))
        has_text_attachments = bool(self._extract_file_attachments(payload))

        if normalized_query:
            return None
        if has_images:
            return "Skill-002"
        if has_text_attachments:
            return "Skill-005"
        return None

    async def _build_image_search_context(
        self, payload: Dict[str, Any], user_id: str, collections: List[view_models.Collection]
    ) -> str:
        dingtalk_settings = await self._settings()
        if not dingtalk_settings["image_search_enabled"]:
            return ""

        image_refs = self._extract_image_urls(payload)
        logger.info(
            "DingTalk image search input enabled=%s image_refs=%s collection_ids=%s",
            settings.dingtalk_image_search_enabled,
            image_refs,
            [collection.id for collection in collections if collection.id],
        )
        if not image_refs or not collections:
            return ""

        contexts = []
        for image_ref in image_refs[:3]:
            try:
                data_uri = await self._download_dingtalk_image_as_data_uri(image_ref, payload)
                if not data_uri:
                    logger.info("DingTalk image ref produced no data uri: %s", image_ref)
                    continue
                results = await image_search_service.search_similar_images(
                    user_id=user_id,
                    collections=collections,
                    image_data_uri=data_uri,
                    top_k=settings.dingtalk_image_search_topk,
                    similarity_threshold=settings.dingtalk_image_search_similarity,
                )
                logger.info("DingTalk image search returned %s results for ref=%s", len(results), image_ref)
                contexts.extend(results)
            except Exception:
                logger.exception("Failed to build DingTalk image search context")

        return await image_search_service.format_image_search_context(
            user_id,
            contexts,
            top_k=settings.dingtalk_image_search_topk,
        )

    async def _upload_dingtalk_attachments_to_chat(
        self, chat_id: str, user_id: str, payload: Dict[str, Any]
    ) -> List[view_models.File]:
        uploaded_files: List[view_models.File] = []
        image_refs = self._extract_image_urls(payload)
        for index, image_ref in enumerate(image_refs[:3], start=1):
            try:
                image_file = await self._build_upload_file_from_dingtalk_image(image_ref, payload, index)
                if not image_file:
                    continue
                document = await chat_document_service.upload_chat_document(chat_id=chat_id, user_id=user_id, file=image_file)
                uploaded_files.append(view_models.File(id=document.id, name=document.name))
                logger.info("Uploaded DingTalk image as chat document chat=%s document=%s ref=%s", chat_id, document.id, image_ref)
            except Exception:
                logger.exception("Failed to upload DingTalk image to chat attachment ref=%s", image_ref)

        file_attachments = self._extract_file_attachments(payload)
        for index, attachment in enumerate(file_attachments[:3], start=1):
            try:
                upload_file = await self._build_upload_file_from_dingtalk_attachment(attachment, payload, index)
                if not upload_file:
                    continue
                document = await chat_document_service.upload_chat_document(chat_id=chat_id, user_id=user_id, file=upload_file)
                uploaded_files.append(view_models.File(id=document.id, name=document.name))
                logger.info(
                    "Uploaded DingTalk file as chat document chat=%s document=%s file=%s",
                    chat_id,
                    document.id,
                    attachment.get("file_name"),
                )
            except Exception:
                logger.exception("Failed to upload DingTalk file attachment=%s", attachment)
        return uploaded_files

    async def _wait_for_chat_documents_ready(
        self,
        files: List[view_models.File],
        timeout_seconds: float = 30.0,
        poll_interval_seconds: float = 1.0,
    ) -> tuple[bool, List[str]]:
        deadline = time.time() + timeout_seconds
        pending_ids = {file.id: file.name or file.id for file in files if file.id}
        failed_files: List[str] = []

        while pending_ids and time.time() < deadline:
            finished_ids: List[str] = []
            for document_id, document_name in pending_ids.items():
                document = await self.db_ops.query_document_by_id(document_id)
                status = getattr(document, "status", None)
                status_value = getattr(status, "value", status)

                if status_value == DocumentStatus.COMPLETE.value:
                    finished_ids.append(document_id)
                elif status_value == DocumentStatus.FAILED.value:
                    failed_files.append(document_name)
                    finished_ids.append(document_id)

            for document_id in finished_ids:
                pending_ids.pop(document_id, None)

            if pending_ids:
                await asyncio.sleep(poll_interval_seconds)

        if pending_ids:
            logger.info("Timed out waiting for DingTalk chat documents to finish indexing: %s", list(pending_ids.values()))
            return False, failed_files
        if failed_files:
            logger.info("Some DingTalk chat documents failed indexing: %s", failed_files)
            return False, failed_files
        return True, []

    @staticmethod
    def _is_image_file(file: view_models.File) -> bool:
        name = (getattr(file, "name", None) or "").lower()
        return name.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"))

    async def _build_upload_file_from_dingtalk_attachment(
        self, attachment: Dict[str, str], payload: Dict[str, Any], index: int
    ) -> Optional[UploadFile]:
        download_code = str(attachment.get("download_code") or "").strip()
        if not download_code:
            return None

        if not self._is_supported_text_attachment(attachment):
            logger.info(
                "Skipped DingTalk non-text attachment file=%s content_type=%s",
                attachment.get("file_name"),
                attachment.get("content_type"),
            )
            return None

        download_url = await self._get_dingtalk_download_url(download_code, payload)
        if not download_url:
            return None

        filename = self._build_dingtalk_attachment_filename(attachment, index)
        content, content_type = await self._download_dingtalk_attachment_file(download_url, filename)
        return UploadFile(
            filename=filename,
            size=len(content),
            headers=Headers({"content-type": content_type}),
            file=io.BytesIO(content),
        )

    async def _build_upload_file_from_dingtalk_image(
        self, image_ref: str, payload: Dict[str, Any], index: int
    ) -> Optional[UploadFile]:
        content: bytes
        content_type: str
        filename: str

        if image_ref.startswith("data:image/"):
            parsed = self._parse_image_data_uri(image_ref, index)
            if not parsed:
                return None
            content, content_type, filename = parsed
        else:
            if image_ref.startswith("http://") or image_ref.startswith("https://"):
                download_url = image_ref
            else:
                download_url = await self._get_dingtalk_download_url(image_ref, payload)
            if not download_url:
                return None
            content, content_type, filename = await self._download_dingtalk_image_file(download_url, index)

        return UploadFile(
            filename=filename,
            size=len(content),
            headers=Headers({"content-type": content_type}),
            file=io.BytesIO(content),
        )

    def _parse_image_data_uri(self, image_ref: str, index: int) -> Optional[tuple[bytes, str, str]]:
        header, _, encoded = image_ref.partition(",")
        if not encoded:
            return None
        content_type = header.split(";", 1)[0].replace("data:", "").strip().lower() or "image/png"
        try:
            content = base64.b64decode(encoded)
        except Exception:
            logger.exception("Failed to decode DingTalk image data uri")
            return None
        return content, content_type, self._build_dingtalk_image_filename(index, content_type)

    async def _download_dingtalk_image_file(self, url: str, index: int) -> tuple[bytes, str, str]:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            content = response.content

        content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if not content_type.startswith("image/"):
            content_type = self._guess_image_content_type(content)
        logger.info("Downloaded DingTalk image bytes=%s content_type=%s", len(content), content_type)
        return content, content_type, self._build_dingtalk_image_filename(index, content_type)

    async def _download_dingtalk_attachment_file(self, url: str, filename: str) -> tuple[bytes, str]:
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            content = response.content

        content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if not content_type or content_type == "application/octet-stream":
            content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        logger.info("Downloaded DingTalk file bytes=%s content_type=%s filename=%s", len(content), content_type, filename)
        return content, content_type

    def _build_dingtalk_image_filename(self, index: int, content_type: str) -> str:
        suffix = mimetypes.guess_extension(content_type) or ".png"
        return f"dingtalk-image-{index}{suffix}"

    def _build_dingtalk_attachment_filename(self, attachment: Dict[str, str], index: int) -> str:
        file_name = str(attachment.get("file_name") or "").strip()
        if file_name:
            return os.path.basename(file_name)

        content_type = str(attachment.get("content_type") or "").strip().lower()
        suffix = mimetypes.guess_extension(content_type) or ".bin"
        return f"dingtalk-file-{index}{suffix}"

    def _is_supported_text_attachment(self, attachment: Dict[str, str]) -> bool:
        file_name = str(attachment.get("file_name") or "").strip().lower()
        content_type = str(attachment.get("content_type") or "").strip().lower()

        if content_type.startswith("image/") or content_type == "application/pdf":
            return False
        if file_name.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg", ".heic", ".tif", ".tiff", ".pdf")):
            return False

        allowed_extensions = {
            ".txt", ".md", ".markdown", ".log", ".csv", ".tsv", ".json", ".jsonl", ".xml", ".yaml", ".yml",
            ".ini", ".cfg", ".conf", ".sql", ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".rb",
            ".php", ".c", ".cc", ".cpp", ".h", ".hpp", ".cs", ".rs", ".sh", ".bat", ".ps1", ".kt", ".swift",
            ".scala", ".r", ".m", ".pl", ".lua", ".vue", ".html", ".htm", ".css", ".scss", ".less", ".sass",
            ".dockerfile", ".env", ".properties", ".gradle", ".pom", ".doc", ".docx",
        }
        allowed_content_prefixes = (
            "text/",
            "application/json",
            "application/xml",
            "application/x-",
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

        if file_name:
            root_name = os.path.basename(file_name)
            if root_name == "dockerfile" or root_name.endswith(".env"):
                return True
            if any(root_name.endswith(ext) for ext in allowed_extensions):
                return True

        return content_type.startswith(allowed_content_prefixes)

    async def _download_dingtalk_image_as_data_uri(self, image_ref: str, payload: Dict[str, Any]) -> str:
        if image_ref.startswith("data:image/"):
            logger.info("DingTalk image ref is already data URI")
            return image_ref
        if image_ref.startswith("http://") or image_ref.startswith("https://"):
            logger.info("DingTalk image ref is direct URL")
            return await self._download_url_as_data_uri(image_ref)

        download_url = await self._get_dingtalk_download_url(image_ref, payload)
        if not download_url:
            logger.warning("DingTalk image download skipped because download url is unavailable")
            return ""
        logger.info("DingTalk image download URL resolved for downloadCode ref")
        return await self._download_url_as_data_uri(download_url)

    async def _get_dingtalk_download_url(self, download_code: str, payload: Dict[str, Any]) -> str:
        token = await self._get_dingtalk_access_token()
        if not token:
            return ""

        dingtalk_settings = await self._settings()
        robot_code = str(payload.get("robotCode") or dingtalk_settings["robot_code"] or "").strip()
        if not robot_code:
            logger.warning("DingTalk image download skipped because robotCode is unavailable")
            return ""

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                "https://api.dingtalk.com/v1.0/robot/messageFiles/download",
                headers={"x-acs-dingtalk-access-token": token, "Content-Type": "application/json"},
                json={"downloadCode": download_code, "robotCode": robot_code},
            )
            response.raise_for_status()
            result = response.json()

        download_url = result.get("downloadUrl") or result.get("download_url")
        if not download_url:
            logger.warning("DingTalk file download API did not return downloadUrl: %s", result)
            return ""
        return str(download_url)

    async def _get_dingtalk_access_token(self) -> str:
        if self._access_token and time.time() < self._access_token_expire_at:
            return self._access_token

        dingtalk_settings = await self._settings()
        app_key = (dingtalk_settings["app_key"] or settings.dingtalk_stream_client_id).strip()
        app_secret = (dingtalk_settings["app_secret"] or settings.dingtalk_stream_client_secret).strip()
        if not app_key or not app_secret:
            logger.warning("DingTalk access token skipped because app key or app secret is missing")
            return ""

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                "https://api.dingtalk.com/v1.0/oauth2/accessToken",
                headers={"Content-Type": "application/json"},
                json={"appKey": app_key, "appSecret": app_secret},
            )
            response.raise_for_status()
            result = response.json()

        token = result.get("accessToken") or result.get("access_token")
        if not token:
            logger.warning("DingTalk access token API did not return a token: %s", result)
            return ""

        expire_in = int(result.get("expireIn") or result.get("expires_in") or 7200)
        self._access_token = str(token)
        self._access_token_expire_at = time.time() + max(expire_in - 600, 60)
        return self._access_token

    async def _download_url_as_data_uri(self, url: str) -> str:
        content, content_type, _ = await self._download_dingtalk_image_file(url, index=1)
        encoded = base64.b64encode(content).decode("utf-8")
        return f"data:{content_type};base64,{encoded}"

    def _guess_image_content_type(self, content: bytes) -> str:
        if content.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if content.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if content.startswith(b"GIF87a") or content.startswith(b"GIF89a"):
            return "image/gif"
        if content.startswith(b"RIFF") and b"WEBP" in content[:16]:
            return "image/webp"
        return "image/png"

    def _extract_text(self, payload: Dict[str, Any]) -> str:
        text = payload.get("text")
        if isinstance(text, dict):
            return str(text.get("content") or text.get("text") or "")
        if isinstance(text, str):
            return text
        return str(payload.get("content") or payload.get("msg") or payload.get("message") or "")

    def _extract_image_urls(self, payload: Dict[str, Any]) -> List[str]:
        urls = []
        msgtype = str(payload.get("msgtype") or payload.get("msgType") or payload.get("messageType") or "").strip().lower()
        for key in ("image", "picture", "photo"):
            value = payload.get(key)
            if isinstance(value, dict):
                for url_key in ("downloadCode", "mediaId", "url", "picUrl"):
                    if value.get(url_key):
                        urls.append(str(value[url_key]))
            elif isinstance(value, str):
                urls.append(value)

        content = payload.get("content")
        if isinstance(content, dict) and msgtype not in {"file", "richtext"}:
            content_type = str(content.get("type") or content.get("msgType") or content.get("tag") or "").strip().lower()
            file_name = str(content.get("fileName") or content.get("file_name") or "").strip()
            if file_name:
                return urls
            if content_type and any(keyword in content_type for keyword in ("file", "attachment", "doc", "link")):
                return urls
            for url_key in ("downloadCode", "mediaId", "url", "picUrl"):
                if content.get(url_key):
                    urls.append(str(content[url_key]))
        return urls

    def _extract_file_attachments(self, payload: Dict[str, Any]) -> List[Dict[str, str]]:
        return self._extract_file_attachments_by_support(payload, supported=True)

    def _extract_unsupported_file_attachments(self, payload: Dict[str, Any]) -> List[Dict[str, str]]:
        return self._extract_file_attachments_by_support(payload, supported=False)

    def _extract_file_attachments_by_support(self, payload: Dict[str, Any], supported: bool) -> List[Dict[str, str]]:
        attachments: List[Dict[str, str]] = []

        content = payload.get("content")
        if isinstance(content, dict):
            attachment = self._extract_file_attachment_from_item(content)
            if attachment and self._is_supported_text_attachment(attachment) is supported:
                attachments.append(attachment)

        rich_text = payload.get("richText")
        if not isinstance(rich_text, list):
            return attachments

        for item in rich_text:
            attachment = self._extract_file_attachment_from_item(item)
            if attachment and self._is_supported_text_attachment(attachment) is supported:
                attachments.append(attachment)
        return attachments

    def _extract_file_attachment_from_item(self, item: Any) -> Optional[Dict[str, str]]:
        if not isinstance(item, dict):
            return None

        item_type = str(item.get("type") or item.get("msgType") or item.get("tag") or "").strip().lower()
        candidate = self._select_file_candidate(item)
        if not candidate:
            return None

        download_code = str(
            candidate.get("downloadCode")
            or candidate.get("download_code")
            or candidate.get("mediaId")
            or candidate.get("media_id")
            or ""
        ).strip()
        if not download_code:
            return None

        if item_type and any(keyword in item_type for keyword in ("image", "picture", "photo")):
            return None

        file_name = str(
            candidate.get("fileName")
            or candidate.get("file_name")
            or candidate.get("name")
            or item.get("text")
            or ""
        ).strip()
        content_type = str(
            candidate.get("fileType")
            or candidate.get("contentType")
            or candidate.get("content_type")
            or ""
        ).strip()
        return {
            "download_code": download_code,
            "file_name": file_name,
            "content_type": content_type,
        }

    def _select_file_candidate(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        nested_keys = ("file", "attachment", "content", "extra", "value", "data")
        for key in nested_keys:
            value = item.get(key)
            if isinstance(value, dict) and self._contains_file_download_code(value):
                return value
        if self._contains_file_download_code(item):
            return item
        return None

    def _contains_file_download_code(self, value: Dict[str, Any]) -> bool:
        return any(value.get(key) for key in ("downloadCode", "download_code", "mediaId", "media_id"))

    def _peer_id(self, payload: Dict[str, Any]) -> str:
        conversation_id = payload.get("conversationId") or payload.get("conversation_id")
        sender_id = payload.get("senderStaffId") or payload.get("senderId") or payload.get("userid")
        if conversation_id and sender_id:
            return f"{conversation_id}:{sender_id}"
        return str(conversation_id or sender_id or payload.get("chatid") or "dingtalk-default")

    def _session_webhook(self, payload: Dict[str, Any]) -> Optional[str]:
        value = payload.get("sessionWebhook") or payload.get("session_webhook")
        return str(value) if value else None

    def _strip_bot_mentions(self, query: str) -> str:
        for mention in ("@SAPilot", "@SAPilot机器人", "@野山小钉"):
            query = query.replace(mention, "")
        return query.strip()

    def _format_dingtalk_query(self, query: str, image_context: str = "") -> str:
        if not image_context:
            return query
        return f"{query}\n\n{image_context}"

    def _text_response(self, content: str) -> Dict[str, Any]:
        return {"msgtype": "text", "text": {"content": content}}

    def _markdown_response(self, title: str, content: str) -> Dict[str, Any]:
        return {"msgtype": "markdown", "markdown": {"title": title, "text": self._limit_markdown(content)}}

    def _limit_markdown(self, content: str) -> str:
        if len(content) <= 18000:
            return content
        return content[:18000] + "\n\n回答较长，已截断。请继续追问获取后续步骤。"

    def _should_search_kb(self, query: str, payload: Dict[str, Any]) -> bool:
        """Decide whether DingTalk message needs knowledge base search.

        Triggers: image upload, explicit search request, SAP/business keywords.
        Default: free conversation.
        """
        image_urls = self._extract_image_urls(payload)
        if image_urls:
            logger.info("DingTalk KB search triggered: image upload")
            return True

        if not query:
            return False

        import re
        normalized = re.sub(r"[\s!！?？。,.，；;:：~～]+", "", query).lower()

        if self._is_non_local_knowledge_base_query(normalized):
            logger.info("DingTalk KB search skipped: non-local knowledge-base question '%s'", query)
            return False

        if self._is_knowledge_base_existence_query(normalized):
            logger.info("DingTalk KB search triggered: knowledge-base existence question '%s'", query)
            return True

        search_triggers = {
            "查一下", "查查", "帮我查", "帮我搜", "搜一下", "搜索", "检索",
            "从知识库查", "知识库查", "查知识库", "搜知识库", "问知识库",
            "知识库", "本地库", "本地知识库",
            "search", "lookup", "find", "check",
        }
        if any(trigger in normalized for trigger in search_triggers):
            logger.info("DingTalk KB search triggered: explicit search '%s'", query)
            return True

        return False

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


class _CollectingMessageQueue:
    def __init__(self):
        self.messages: List[Dict[str, Any]] = []
        self.tool_call_results: List[Dict[str, Any]] = []

    async def put(self, message):
        if message is None:
            return
        self.messages.append(message)
        if isinstance(message, dict) and message.get("type") == "tool_call_result":
            self.tool_call_results.append(message)

    async def close(self):
        return None


dingtalk_bot_service = DingTalkBotService()
