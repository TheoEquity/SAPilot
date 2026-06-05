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

import json
import logging
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aperag.db import models as db_models
from aperag.db.ops import AsyncDatabaseOps, async_db_ops, db_ops
from aperag.exceptions import ResourceNotFoundException, ValidationException

logger = logging.getLogger(__name__)

DINGTALK_SETTING_KEYS = {
    "dingtalk_enabled",
    "dingtalk_webhook_secret",
    "dingtalk_outgoing_webhook_url",
    "dingtalk_outgoing_webhook_secret",
    "dingtalk_bot_user_id",
    "dingtalk_bot_id",
    "dingtalk_response_mode",
    "dingtalk_robot_code",
    "dingtalk_app_key",
    "dingtalk_app_secret",
}


class SettingService:
    """Service for handling global settings"""

    def __init__(self, session: AsyncSession = None):
        if session is None:
            self.db_ops = async_db_ops
        else:
            self.db_ops = AsyncDatabaseOps(session)

    async def get_setting(self, key: str) -> Any | None:
        setting = await self.db_ops.query_setting(key)
        if not setting or setting.value is None:
            return None
        return json.loads(setting.value)

    async def update_setting(self, key: str, value: Any):
        await self.db_ops.update_setting(key, json.dumps(value))

    async def get_mineru_api_token(self) -> str | None:
        return await self.get_setting("mineru_api_token")

    async def update_mineru_api_token(self, token: str):
        await self.update_setting("mineru_api_token", token)

    async def get_use_mineru(self) -> bool:
        return await self.get_setting("use_mineru") or False

    async def update_use_mineru(self, use_mineru: bool):
        await self.update_setting("use_mineru", use_mineru)

    async def get_use_doc_ray(self) -> bool:
        return await self.get_setting("use_doc_ray") or False

    async def update_use_doc_ray(self, use_doc_ray: bool):
        await self.update_setting("use_doc_ray", use_doc_ray)

    async def get_use_markitdown(self) -> bool:
        return await self.get_setting("use_markitdown") or True

    async def update_use_markitdown(self, use_markitdown: bool):
        await self.update_setting("use_markitdown", use_markitdown)

    async def get_all_settings(self) -> dict:
        settings = await self.db_ops.query_all_settings()
        return {s.key: json.loads(s.value) for s in settings}

    def get_all_settings_sync(self) -> dict:
        settings = db_ops.query_all_settings()
        return {s.key: json.loads(s.value) for s in settings}

    async def update_settings(self, settings: dict):
        for key, value in settings.items():
            if value is not None:
                await self.update_setting(key, value)

    async def update_admin_settings(self, settings: dict, admin_user_id: str):
        dingtalk_settings = {key: value for key, value in settings.items() if key in DINGTALK_SETTING_KEYS}
        if dingtalk_settings:
            await self._validate_and_protect_dingtalk_bot(dingtalk_settings, admin_user_id)
            settings = {**settings, "dingtalk_bot_user_id": admin_user_id}
        await self.update_settings(settings)

    async def get_dingtalk_bound_bot_id(self) -> str | None:
        bot_id = await self.get_setting("dingtalk_bot_id")
        if not bot_id:
            return None
        return str(bot_id).strip() or None

    async def _validate_and_protect_dingtalk_bot(self, settings: dict, admin_user_id: str):
        enabled = settings.get("dingtalk_enabled")
        bot_id = (settings.get("dingtalk_bot_id") or "").strip()
        if enabled and not bot_id:
            raise ValidationException("DingTalk Agent Bot is required when DingTalk integration is enabled")
        if not bot_id:
            return

        async def _operation(session):
            stmt = select(db_models.Bot).where(
                db_models.Bot.id == bot_id,
                db_models.Bot.user == admin_user_id,
                db_models.Bot.status != db_models.BotStatus.DELETED,
            )
            result = await session.execute(stmt)
            bot = result.scalars().first()
            if not bot:
                logger.warning(
                    f"Referenced DingTalk Bot '{bot_id}' not found for user {admin_user_id}, clearing binding settings"
                )
                settings.pop("dingtalk_bot_id", None)
                settings.pop("dingtalk_enabled", None)
                return
            if bot.type != db_models.BotType.AGENT:
                raise ValidationException("DingTalk integration can only bind an Agent Bot")
            if not bot.is_protected:
                bot.is_protected = True
                session.add(bot)

        await self.db_ops.execute_with_transaction(_operation)

    async def test_mineru_token(self, token: str) -> dict:
        """Test the MinerU API token."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    "https://mineru.net/api/v4/extract-results/batch/test-token",
                    headers={"Authorization": f"Bearer {token}"},
                )
                return {"status_code": response.status_code, "data": response.json()}
            except httpx.RequestError as e:
                return {"status_code": 500, "data": {"msg": f"Request failed: {e}"}}


setting_service = SettingService()
