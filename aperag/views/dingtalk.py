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

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from aperag.service.dingtalk_bot_service import dingtalk_bot_service

router = APIRouter(tags=["dingtalk"])


@router.api_route("/dingtalk/bot/callback", methods=["GET", "HEAD"])
async def dingtalk_bot_callback_check():
    return {"status": "ok", "service": "sapilot-dingtalk"}


@router.post("/dingtalk/bot/callback")
async def dingtalk_bot_callback(request: Request):
    body = await request.body()
    if not body:
        return JSONResponse({"success": True, "status": "ok"})

    try:
        payload = json.loads(body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JSONResponse({"success": True, "status": "ok"})

    if not payload:
        return JSONResponse({"success": True, "status": "ok"})

    timestamp = request.query_params.get("timestamp") or request.headers.get("timestamp")
    sign = request.query_params.get("sign") or request.headers.get("sign")
    return await dingtalk_bot_service.handle_callback(payload, timestamp, sign)
