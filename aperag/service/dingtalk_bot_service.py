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

import base64
import hashlib
import hmac
import json
import logging
import time
import urllib.parse
import uuid
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy import and_, select

from aperag.config import settings
from aperag.context.context import ContextManager
from aperag.db import models as db_models
from aperag.db.ops import async_db_ops
from aperag.llm.embed.base_embedding import get_collection_embedding_service_sync
from aperag.llm.llm_error_types import EmbeddingError, ProviderNotFoundError
from aperag.query.query import DocumentWithScore
from aperag.schema import view_models
from aperag.service.agent_chat_service import AgentChatService
from aperag.service.prompt_template_service import prompt_template_service
from aperag.utils.utils import generate_vector_db_collection_name

logger = logging.getLogger(__name__)


class DingTalkBotService:
    """Handle DingTalk bot callbacks and route them into SAPilot Agent chat."""

    def __init__(self):
        self.db_ops = async_db_ops
        self.agent_chat_service = AgentChatService()
        self._access_token: Optional[str] = None
        self._access_token_expire_at = 0.0

    def verify_signature(self, timestamp: Optional[str], sign: Optional[str]) -> bool:
        if not settings.dingtalk_webhook_secret:
            return True
        if not timestamp or not sign:
            return False

        string_to_sign = f"{timestamp}\n{settings.dingtalk_webhook_secret}".encode("utf-8")
        digest = hmac.new(settings.dingtalk_webhook_secret.encode("utf-8"), string_to_sign, hashlib.sha256).digest()
        expected = urllib.parse.quote_plus(base64.b64encode(digest))
        return hmac.compare_digest(expected, sign)

    async def handle_callback(
        self, payload: Dict[str, Any], timestamp: Optional[str], sign: Optional[str]
    ) -> Dict[str, Any]:
        logger.info("Received DingTalk callback with keys: %s", sorted(payload.keys()))
        if not settings.dingtalk_enabled:
            return self._text_response("SAPilot 钉钉机器人尚未启用。")
        if not self.verify_signature(timestamp, sign):
            return self._text_response("钉钉消息签名校验失败。")

        user_id = settings.dingtalk_bot_user_id.strip()
        bot_id = settings.dingtalk_bot_id.strip()
        if not user_id:
            return self._text_response("SAPilot 钉钉机器人未配置 DINGTALK_BOT_USER_ID。")

        bot = await self.db_ops.query_bot(user_id, bot_id) if bot_id else await self.find_default_agent_bot(user_id)
        if not bot:
            return self._text_response("SAPilot 钉钉机器人绑定的 Bot 不存在，请配置 DINGTALK_BOT_ID 或默认 Agent。")
        if bot.type != db_models.BotType.AGENT:
            return self._text_response("SAPilot 钉钉机器人需要绑定 Agent 类型 Bot。")

        query = self._build_query(payload)
        if not query:
            return self._text_response("请发送 SAP 运维、开发问题、日志或报错截图。")

        logger.info("Processing DingTalk message for bot %s, chat payload peer %s", bot.id, self._peer_id(payload))
        session_webhook = self._session_webhook(payload)
        if settings.dingtalk_response_mode == "webhook" and session_webhook:
            await self.send_text("SAPilot：收到，正在分析...", webhook_url=session_webhook)

        bot_config = self._parse_bot_config(bot)
        default_collections = await self._default_collections(user_id, bot_config)
        image_context = await self._build_image_search_context(payload, user_id, default_collections)
        chat = await self._get_or_create_dingtalk_chat(user_id, bot.id, payload)
        formatted_query = self._format_dingtalk_query(query, image_context=image_context)
        answer = await self._ask_agent(
            user_id,
            bot,
            chat.id,
            formatted_query,
            bot_config=bot_config,
            default_collections=default_collections,
        )
        if settings.dingtalk_response_mode == "webhook":
            answer = f"SAPilot：{answer}"
            logger.info("DingTalk answer length=%s prefix=%r", len(answer), answer[:120])
            await self.send_text(answer, webhook_url=session_webhook)
            return {}
        return self._markdown_response("SAPilot 现场问诊", answer)

    async def send_markdown(self, title: str, content: str) -> Dict[str, Any]:
        return await self._send_outgoing_message(self._markdown_response(title, content))

    async def send_text(self, content: str, webhook_url: Optional[str] = None) -> Dict[str, Any]:
        return await self._send_outgoing_message(self._text_response(content), webhook_url=webhook_url)

    async def _send_outgoing_message(
        self, message: Dict[str, Any], webhook_url: Optional[str] = None
    ) -> Dict[str, Any]:
        webhook_url = (webhook_url or settings.dingtalk_outgoing_webhook_url).strip()
        if not webhook_url:
            raise ValueError("DINGTALK_OUTGOING_WEBHOOK_URL is required to send DingTalk messages")

        url = self._signed_outgoing_url(webhook_url)
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=message)
            response.raise_for_status()
            result = response.json()

        if result.get("errcode") not in (None, 0):
            raise ValueError(f"DingTalk webhook returned error: {result}")
        logger.info("Sent DingTalk outgoing message successfully: %s", result)
        return result

    def _signed_outgoing_url(self, webhook_url: str) -> str:
        secret = settings.dingtalk_outgoing_webhook_secret.strip()
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
        bot_config: Optional[view_models.BotConfig] = None,
        default_collections: Optional[List[view_models.Collection]] = None,
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
            web_search_enabled=settings.dingtalk_sap_community_search_enabled,
            language="zh-CN",
            files=[],
        )

        message_id = str(uuid.uuid4())
        queue = _CollectingMessageQueue()
        trace_id = await self.agent_chat_service.register_message_queue(
            agent_message.language, chat_id, message_id, queue
        )

        try:
            result = await self.agent_chat_service.process_agent_message(
                agent_message,
                user_id,
                chat_id,
                message_id,
                queue,
                bot_config=bot_config,
                default_collections=default_collections,
                resolved_system_prompt=resolved_system_prompt,
                resolved_query_prompt=resolved_query_prompt,
            )
            ai_response = result.get("content") or "未生成有效回答。"
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

        parts = []
        if text:
            parts.append(text)
        if image_urls:
            parts.append("用户上传了报错截图，请结合图片信息分析。")
            parts.extend([f"图片地址：{url}" for url in image_urls])
        if not parts and msgtype:
            parts.append(f"收到钉钉 {msgtype} 类型消息，请提示用户补充 SAP 问题、日志或截图。")

        query = "\n".join(parts)
        return self._strip_bot_mentions(query)

    async def _build_image_search_context(
        self, payload: Dict[str, Any], user_id: str, collections: List[view_models.Collection]
    ) -> str:
        if not settings.dingtalk_image_search_enabled:
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
                results = await self._search_similar_images(
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

        return self._format_image_search_context(contexts)

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

        robot_code = str(payload.get("robotCode") or settings.dingtalk_stream_client_id or "").strip()
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

        app_key = (settings.dingtalk_app_key or settings.dingtalk_stream_client_id).strip()
        app_secret = (settings.dingtalk_app_secret or settings.dingtalk_stream_client_secret).strip()
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
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            content = response.content

        content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
        if not content_type.startswith("image/"):
            content_type = self._guess_image_content_type(content)
        logger.info("Downloaded DingTalk image bytes=%s content_type=%s", len(content), content_type)
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

    async def _search_similar_images(
        self,
        user_id: str,
        collections: List[view_models.Collection],
        image_data_uri: str,
        top_k: int,
        similarity_threshold: float,
    ) -> List[DocumentWithScore]:
        results: List[DocumentWithScore] = []
        for collection_view in collections:
            collection_id = collection_view.id
            if not collection_id:
                continue
            collection = await self.db_ops.query_collection(user_id, collection_id)
            if not collection:
                continue
            try:
                embedding_model, _ = get_collection_embedding_service_sync(collection)
                if not embedding_model.is_multimodal():
                    logger.info("DingTalk image search skipped non-multimodal collection %s", collection_id)
                    continue
                vector = embedding_model.embed_query(image_data_uri)
                collection_name = generate_vector_db_collection_name(collection.id)
                vectordb_ctx = json.loads(settings.vector_db_context)
                vectordb_ctx["collection"] = collection_name
                context_manager = ContextManager(collection_name, embedding_model, settings.vector_db_type, vectordb_ctx)
                collection_results = context_manager.query(
                    "uploaded_dingtalk_image",
                    score_threshold=similarity_threshold,
                    topk=max(top_k * 2, top_k),
                    vector=vector,
                    index_types=["vision"],
                )
                logger.info(
                    "DingTalk image search collection=%s raw_results=%s top_score=%s",
                    collection_id,
                    len(collection_results),
                    collection_results[0].score if collection_results else None,
                )
                for item in collection_results:
                    if item.metadata is None:
                        item.metadata = {}
                    item.metadata["recall_type"] = "vision_search"
                    item.metadata["collection_title"] = collection_view.title or collection.title
                results.extend(collection_results)
            except (ProviderNotFoundError, EmbeddingError) as e:
                logger.warning("DingTalk image search skipped for collection %s: %s", collection_id, e)
            except Exception:
                logger.exception("DingTalk image search failed for collection %s", collection_id)

        results.sort(key=lambda item: item.score if item.score is not None else 0, reverse=True)
        return self._deduplicate_image_results(results)[:top_k]

    def _deduplicate_image_results(self, results: List[DocumentWithScore]) -> List[DocumentWithScore]:
        seen = set()
        deduplicated = []
        for item in results:
            metadata = item.metadata or {}
            key = (metadata.get("collection_id"), metadata.get("document_id"), metadata.get("asset_id"))
            if key in seen:
                continue
            seen.add(key)
            deduplicated.append(item)
        return deduplicated

    def _format_image_search_context(self, results: List[DocumentWithScore]) -> str:
        if not results:
            return ""

        lines = ["相似报错截图检索结果："]
        for idx, item in enumerate(results[: settings.dingtalk_image_search_topk], start=1):
            metadata = item.metadata or {}
            score = f"{item.score:.3f}" if isinstance(item.score, (int, float)) else "未知"
            source = metadata.get("source") or metadata.get("name") or "未知来源"
            collection_title = metadata.get("collection_title") or metadata.get("collection_id") or "未知知识库"
            asset_id = metadata.get("asset_id") or ""
            document_id = metadata.get("document_id") or ""
            content = (item.text or "").strip()
            if len(content) > 500:
                content = content[:500] + "..."
            lines.append(
                f"{idx}. 相似度 {score}，知识库：{collection_title}，来源：{source}，document_id：{document_id}，asset_id：{asset_id}"
            )
            if content:
                lines.append(f"关联说明：{content}")
        return "\n".join(lines)

    def _extract_text(self, payload: Dict[str, Any]) -> str:
        text = payload.get("text")
        if isinstance(text, dict):
            return str(text.get("content") or text.get("text") or "")
        if isinstance(text, str):
            return text
        return str(payload.get("content") or payload.get("msg") or payload.get("message") or "")

    def _extract_image_urls(self, payload: Dict[str, Any]) -> List[str]:
        urls = []
        for key in ("image", "picture", "photo"):
            value = payload.get(key)
            if isinstance(value, dict):
                for url_key in ("downloadCode", "mediaId", "url", "picUrl"):
                    if value.get(url_key):
                        urls.append(str(value[url_key]))
            elif isinstance(value, str):
                urls.append(value)

        content = payload.get("content")
        if isinstance(content, dict):
            for url_key in ("downloadCode", "mediaId", "url", "picUrl"):
                if content.get(url_key):
                    urls.append(str(content[url_key]))
        return urls

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
        image_section = f"\n\n{image_context}" if image_context else ""
        community_instruction = ""
        if settings.dingtalk_sap_community_search_enabled:
            community_instruction = """
5. 如知识库信息不足，使用 web_search 限定 source=community.sap.com 搜索 SAP Community；必要时再用 source=help.sap.com 核对官方文档。
6. 引用外部资料时保留来源链接，并优先总结可执行处理步骤。"""

        return f"""{query}{image_section}

请按钉钉现场问诊场景回答：
1. 回答控制在 500 字以内。
2. 先给最可能原因，再给 3 到 5 条处理步骤。
3. 信息不足时列出需要补充的关键字段。
4. 避免长表格和大段背景说明。{community_instruction}"""

    def _text_response(self, content: str) -> Dict[str, Any]:
        return {"msgtype": "text", "text": {"content": content}}

    def _markdown_response(self, title: str, content: str) -> Dict[str, Any]:
        return {"msgtype": "markdown", "markdown": {"title": title, "text": self._limit_markdown(content)}}

    def _limit_markdown(self, content: str) -> str:
        if len(content) <= 18000:
            return content
        return content[:18000] + "\n\n回答较长，已截断。请继续追问获取后续步骤。"


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
