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
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from aperag.db.models import User
from aperag.service.prompt_template_service import prompt_template_service
from aperag.service.setting_service import DINGTALK_SETTING_KEYS, setting_service
from aperag.views.auth import get_current_admin

logger = logging.getLogger(__name__)

router = APIRouter(tags=["backup"])

DINGTALK_SECRET_KEYS = {
    "dingtalk_webhook_secret",
    "dingtalk_outgoing_webhook_secret",
    "dingtalk_app_secret",
}


class ExportPayload(BaseModel):
    scope: List[str] = Field(..., description="Export scopes: bots, prompts, settings")
    bots: Optional[List[str]] = Field(None, description="Specific bot IDs to export (export all if omitted)")
    include_secrets: bool = Field(False, description="Include secret fields like DingTalk secrets")


class SettingsImportPayload(BaseModel):
    settings: Dict[str, Any] = Field(..., description="Settings key-value pairs to import")


class PromptsImportPayload(BaseModel):
    prompts: Dict[str, str] = Field(..., description="Prompt type to content mapping")


@router.post("/backup/export", tags=["backup"])
async def export_backup(
    request: Request,
    payload: ExportPayload,
    user: User = Depends(get_current_admin),
) -> Dict[str, Any]:
    """
    Export system configuration as JSON.

    Supports exporting:
    - bots: Bot definitions (agent configuration)
    - prompts: User prompt templates
    - settings: System settings (DingTalk, parser, etc.)

    Secret fields (DingTalk webhook secrets, app secrets) are excluded
    unless include_secrets=True.
    """
    result: Dict[str, Any] = {}
    user_id = str(user.id)

    if "settings" in payload.scope:
        all_settings = await setting_service.get_all_settings()
        if not payload.include_secrets:
            all_settings = {k: v for k, v in all_settings.items() if k not in DINGTALK_SECRET_KEYS}
        result["settings"] = all_settings

    if "prompts" in payload.scope:
        prompts_data = await prompt_template_service.get_user_prompts(user_id=user_id)
        result["prompts"] = {k: v["content"] for k, v in prompts_data.items() if v.get("content")}

    if "bots" in payload.scope:
        from aperag.db import models as db_models
        from aperag.db.ops import async_db_ops

        bot_configs = await async_db_ops.query_bot_list(user_id=user_id)
        if payload.bots:
            bot_configs = [b for b in bot_configs if b.id in payload.bots]

        result["bots"] = []
        for bot in bot_configs:
            bot_data = {
                "id": bot.id,
                "title": bot.title,
                "type": bot.type.value if hasattr(bot.type, "value") else bot.type,
                "description": bot.description,
                "config": json.loads(bot.config) if bot.config else None,
            }
            result["bots"].append(bot_data)

    result["has_secrets"] = payload.include_secrets
    return result


@router.post("/backup/import/settings", tags=["backup"])
async def import_settings(
    request: Request,
    payload: SettingsImportPayload,
    user: User = Depends(get_current_admin),
) -> Dict[str, Any]:
    """
    Import system settings from backup JSON.
    """
    admin_user_id = str(user.id)

    dingtalk_settings = {k: v for k, v in payload.settings.items() if k in DINGTALK_SETTING_KEYS}
    non_dingtalk_settings = {k: v for k, v in payload.settings.items() if k not in DINGTALK_SETTING_KEYS}

    if non_dingtalk_settings:
        await setting_service.update_settings(non_dingtalk_settings)

    if dingtalk_settings:
        await setting_service.update_admin_settings(dingtalk_settings, admin_user_id)

    imported_count = len(payload.settings)
    return {
        "message": f"Settings imported successfully",
        "imported_count": imported_count,
    }


@router.post("/backup/import/prompts", tags=["backup"])
async def import_prompts(
    request: Request,
    payload: PromptsImportPayload,
    user: User = Depends(get_current_admin),
) -> Dict[str, Any]:
    """
    Import prompt templates from backup JSON.
    """
    user_id = str(user.id)
    updated = await prompt_template_service.update_user_prompts(user_id=user_id, prompts=payload.prompts)
    return {
        "message": "Prompts imported successfully",
        "imported_count": len(updated),
        "updated": updated,
    }
