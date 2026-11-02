"""Real history message creation with Redis persistence replaced by a local spy."""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from aperag.chat.history import message_to_storage_dict, storage_dict_to_message  # noqa: E402
from aperag.utils.history import RedisChatMessageHistory  # noqa: E402


def local_history():
    # Skip the Redis-only constructor; message creation remains the real method.
    history = RedisChatMessageHistory.__new__(RedisChatMessageHistory)
    history.session_id = "flow-chat"
    history.add_stored_message = AsyncMock()
    return history


@pytest.mark.parametrize("files", ["omitted", None, [], [{"id": "attachment", "name": "SAP.txt"}]])
def test_user_history_accepts_absent_files_and_preserves_attachments(files):
    history = local_history()
    kwargs = {} if files == "omitted" else {"files": files}
    asyncio.run(history.add_user_message("SAP query", "flow-message", **kwargs))
    history.add_stored_message.assert_awaited_once()
    stored = history.add_stored_message.await_args.args[0]
    expected = files if isinstance(files, list) else []
    assert stored.files == expected
    assert stored.chat_id == "flow-chat" and stored.message_id == "flow-message"
    assert stored.role == "human" and stored.get_main_content() == "SAP query"
    assert storage_dict_to_message(message_to_storage_dict(stored)).files == expected
    if expected:
        assert files == [{"id": "attachment", "name": "SAP.txt"}]


def test_assistant_history_defaults_still_create_valid_message():
    history = local_history()
    asyncio.run(history.add_ai_message("SAP answer", "flow-chat", "flow-message"))
    history.add_stored_message.assert_awaited_once()
    stored = history.add_stored_message.await_args.args[0]
    assert stored.role == "ai" and stored.get_main_content() == "SAP answer"
    assert stored.files == [] and len(stored.parts) == 1
    assert stored.parts[0].references == [] and stored.parts[0].urls == []
