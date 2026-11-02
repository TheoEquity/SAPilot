# Copyright 2025 ApeCloud, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

import asyncio
import json
import logging
import os
import sys

from dotenv import load_dotenv

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

load_dotenv(os.path.join(ROOT_DIR, ".env"), override=True)

import dingtalk_stream  # noqa: E402

from aperag.service.dingtalk_bot_service import dingtalk_bot_service  # noqa: E402

logger = logging.getLogger("sapilot.dingtalk_stream")


class LoggingDingTalkStreamClient(dingtalk_stream.DingTalkStreamClient):
    async def route_message(self, json_message):
        logger.info(
            "Received raw DingTalk stream frame type=%s topic=%s keys=%s",
            json_message.get("type"),
            json_message.get("headers", {}).get("topic"),
            sorted(json_message.keys()),
        )
        logger.debug("Raw DingTalk stream frame=%s", json.dumps(json_message, ensure_ascii=False)[:2000])
        return await super().route_message(json_message)


class SAPilotChatbotHandler(dingtalk_stream.ChatbotHandler):
    async def process(self, callback_message: dingtalk_stream.CallbackMessage):
        incoming = dingtalk_stream.ChatbotMessage.from_dict(callback_message.data)
        payload = incoming.to_dict()
        logger.info(
            "Received DingTalk stream message robotCode=%s conversationType=%s msgtype=%s sender=%s text=%r keys=%s",
            payload.get("robotCode"),
            payload.get("conversationType"),
            payload.get("msgtype") or payload.get("msgType") or payload.get("messageType"),
            payload.get("senderStaffId") or payload.get("senderId"),
            payload.get("text", {}).get("content") if isinstance(payload.get("text"), dict) else payload.get("text"),
            sorted(payload.keys()),
        )
        if any(key in payload for key in ("image", "picture", "photo", "content")):
            logger.info("DingTalk message media payload=%s", json.dumps(payload, ensure_ascii=False)[:4000])

        asyncio.create_task(self._handle_message(payload))
        return dingtalk_stream.AckMessage.STATUS_OK, "ok"

    async def _handle_message(self, payload):
        try:
            await dingtalk_bot_service.handle_callback(payload, timestamp=None, sign=None)
        except Exception:
            logger.exception("Failed to handle DingTalk stream message")


class SAPilotEventHandler(dingtalk_stream.EventHandler):
    async def process(self, event: dingtalk_stream.EventMessage):
        logger.info(
            "Received DingTalk stream event type=%s data_keys=%s",
            getattr(event, "event_type", None),
            sorted(event.data.keys()) if isinstance(event.data, dict) else type(event.data).__name__,
        )
        return dingtalk_stream.AckMessage.STATUS_OK, "ok"


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")

    client_id = os.getenv("DINGTALK_STREAM_CLIENT_ID", "").strip()
    client_secret = os.getenv("DINGTALK_STREAM_CLIENT_SECRET", "").strip()
    topic = os.getenv("DINGTALK_STREAM_TOPIC", dingtalk_stream.ChatbotMessage.TOPIC).strip()
    if not client_id or not client_secret:
        raise RuntimeError("DINGTALK_STREAM_CLIENT_ID and DINGTALK_STREAM_CLIENT_SECRET are required")

    credential = dingtalk_stream.Credential(client_id, client_secret)
    client = LoggingDingTalkStreamClient(credential)
    client.register_callback_handler(topic, SAPilotChatbotHandler())
    client.register_callback_handler(dingtalk_stream.ChatbotMessage.DELEGATE_TOPIC, SAPilotChatbotHandler())
    client.register_all_event_handler(SAPilotEventHandler())
    logger.info("Starting DingTalk stream bot with topic=%s", topic)
    client.start_forever()


if __name__ == "__main__":
    main()
