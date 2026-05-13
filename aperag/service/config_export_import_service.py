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
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from aperag.db import models as db_models
from aperag.db.ops import async_db_ops
from aperag.schema import view_models
from aperag.schema.view_models import Bot, BotConfig, Collection
from aperag.service.bot_service import bot_service
from aperag.service.setting_service import DINGTALK_SETTING_KEYS, setting_service

logger = logging.getLogger(__name__)

EXPORT_VERSION = "1.0"

DINGTALK_BOT_ID_TITLE_KEY = "_dingtalk_bot_id_title"


class ConfigExportImportService:
    """Service for exporting and importing bot configurations and settings."""

    def __init__(self):
        self.db_ops = async_db_ops

    async def export_config(self, user_id: str) -> Dict[str, Any]:
        """Export all bots, collection metadata, and DingTalk settings for a user."""
        bots = await self.db_ops.query_bots([user_id])
        bot_items = []
        collection_titles: set[str] = set()

        for bot in bots:
            bot_dict = await self._serialize_bot(bot, collection_titles)
            bot_items.append(bot_dict)

        all_settings = await setting_service.get_all_settings()
        dingtalk_settings = {k: all_settings.get(k) for k in DINGTALK_SETTING_KEYS if k in all_settings}

        if dingtalk_settings.get("dingtalk_bot_id"):
            bound_bot = await self.db_ops.query_bot(user_id, dingtalk_settings["dingtalk_bot_id"])
            if bound_bot:
                dingtalk_settings[DINGTALK_BOT_ID_TITLE_KEY] = bound_bot.title

        return {
            "version": EXPORT_VERSION,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "user_id": user_id,
            "bots": bot_items,
            "dingtalk_settings": dingtalk_settings,
        }

    async def import_config(
        self,
        user_id: str,
        data: Dict[str, Any],
        mode: str = "merge",
    ) -> Dict[str, Any]:
        """Import bots, collection metadata, and DingTalk settings.

        Args:
            user_id: The user who owns the imported resources.
            data: Exported configuration data.
            mode: "merge" (skip existing by title) or "replace" (delete existing first).
        """
        version = data.get("version", "unknown")
        if version != EXPORT_VERSION:
            logger.warning("Export version mismatch: expected %s, got %s", EXPORT_VERSION, version)

        result = {"bots_created": 0, "bots_skipped": 0, "errors": []}
        title_to_id: Dict[str, str] = {}

        if mode == "replace":
            await self._delete_existing_bots(user_id)

        bot_items = data.get("bots", [])
        for bot_data in bot_items:
            try:
                bot_id = await self._import_bot(user_id, bot_data, title_to_id, mode)
                if bot_id:
                    result["bots_created"] += 1
            except Exception as e:
                logger.exception("Failed to import bot %s", bot_data.get("title"))
                result["errors"].append(f"Bot {bot_data.get('title')}: {str(e)}")

        dingtalk_settings = data.get("dingtalk_settings", {})
        if dingtalk_settings:
            try:
                await self._import_dingtalk_settings(user_id, dingtalk_settings, title_to_id)
            except Exception as e:
                logger.exception("Failed to import DingTalk settings")
                result["errors"].append(f"DingTalk settings: {str(e)}")

        return result

    async def _delete_existing_bots(self, user_id: str):
        """Delete all existing bots for the user."""
        bots = await self.db_ops.query_bots([user_id])
        for bot in bots:
            try:
                await bot_service.delete_bot(user_id, bot.id)
            except Exception:
                logger.warning("Failed to delete existing bot %s", bot.id)

    async def _serialize_bot(self, bot: db_models.Bot, collection_titles: set) -> Dict[str, Any]:
        """Serialize a bot to a dictionary for export."""
        bot_dict = {
            "title": bot.title,
            "type": bot.type,
            "description": bot.description,
            "is_default": bot.is_default,
            "is_protected": bot.is_protected,
        }

        if bot.config:
            try:
                config = json.loads(bot.config)
                config = self._strip_collection_ids(config, collection_titles)
                bot_dict["config"] = config
            except (json.JSONDecodeError, ValueError):
                logger.warning("Failed to parse config for bot %s", bot.id)

        return bot_dict

    def _strip_collection_ids(self, config: Dict[str, Any], collection_titles: set) -> Dict[str, Any]:
        """Remove collection IDs from config but keep titles for lookup."""
        if "agent" in config and isinstance(config["agent"], dict):
            agent = config["agent"]
            if "collections" in agent and isinstance(agent["collections"], list):
                new_collections = []
                for col in agent["collections"]:
                    if isinstance(col, dict):
                        if col.get("title"):
                            collection_titles.add(col["title"])
                        stripped = {
                            "title": col.get("title"),
                            "type": col.get("type"),
                            "description": col.get("description"),
                        }
                        new_collections.append(stripped)
                agent["collections"] = new_collections
        return config

    async def _import_bot(
        self,
        user_id: str,
        bot_data: Dict[str, Any],
        title_to_id: Dict[str, str],
        mode: str,
    ) -> Optional[str]:
        """Import a single bot. Returns the new bot ID or None if skipped."""
        title = bot_data.get("title")
        if not title:
            return None

        if mode == "merge":
            existing = await self._find_bot_by_title(user_id, title)
            if existing:
                logger.info("Skipping existing bot: %s", title)
                title_to_id[title] = existing.id
                return None

        bot_create = view_models.BotCreate(
            title=title,
            type=bot_data.get("type"),
            description=bot_data.get("description"),
            is_default=bot_data.get("is_default", False),
            is_protected=bot_data.get("is_protected", False),
        )

        config_data = bot_data.get("config")
        if config_data:
            config_data = self._resolve_collection_ids(config_data, title_to_id)
            try:
                bot_create.config = view_models.BotConfig(**config_data)
            except Exception:
                logger.warning("Failed to parse config for bot %s, importing without config", title)

        created_bot = await bot_service.create_bot(user_id, bot_create)
        title_to_id[title] = created_bot.id
        return created_bot.id

    async def _find_bot_by_title(self, user_id: str, title: str) -> Optional[db_models.Bot]:
        """Find a bot by title for the user."""
        bots = await self.db_ops.query_bots([user_id])
        for bot in bots:
            if bot.title == title and bot.status != db_models.BotStatus.DELETED:
                return bot
        return None

    def _resolve_collection_ids(
        self, config: Dict[str, Any], title_to_id: Dict[str, str]
    ) -> Dict[str, Any]:
        """Resolve collection references by title during import."""
        if "agent" in config and isinstance(config["agent"], dict):
            agent = config["agent"]
            if "collections" in agent and isinstance(agent["collections"], list):
                resolved = []
                for col in agent["collections"]:
                    if isinstance(col, dict) and col.get("title") and col["title"] in title_to_id:
                        resolved.append({"id": title_to_id[col["title"]]})
                    elif isinstance(col, dict) and col.get("id"):
                        resolved.append(col)
                agent["collections"] = resolved
        return config

    async def _import_dingtalk_settings(
        self,
        user_id: str,
        dingtalk_settings: Dict[str, Any],
        title_to_id: Dict[str, str],
    ):
        """Import DingTalk settings, resolving bot ID by title."""
        bot_id_title = dingtalk_settings.pop(DINGTALK_BOT_ID_TITLE_KEY, None)
        if bot_id_title and bot_id_title in title_to_id:
            dingtalk_settings["dingtalk_bot_id"] = title_to_id[bot_id_title]
        elif bot_id_title:
            existing = await self._find_bot_by_title(user_id, bot_id_title)
            if existing:
                dingtalk_settings["dingtalk_bot_id"] = existing.id

        for key, value in dingtalk_settings.items():
            if value is not None:
                await setting_service.update_setting(key, value)


config_export_import_service = ConfigExportImportService()
