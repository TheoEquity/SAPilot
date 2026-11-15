"""Store a pending FAQ choice in the authenticated chat's Redis state."""

import json
from dataclasses import asdict, dataclass

from aperag.utils.history import get_async_redis_client

FAQ_CHOICE_LABEL = "是否需要我从专业角度扩展解答？"
FAQ_ACTIONS = {"faq_expand", "faq_end"}
FAQ_TEXT_ACTIONS = {"是，专业扩展": "faq_expand", "否，结束": "faq_end"}
_CHOICE_TTL = 1800


@dataclass(frozen=True)
class PendingFaqChoice:
    turn_id: str
    query: str
    answer: str


def _key(user: str, chat_id: str) -> str:
    return f"sapilot:faq-choice:{user}:{chat_id}"


async def begin_faq_choice_turn(user: str, chat_id: str, turn_id: str) -> None:
    await get_async_redis_client().set(_key(user, chat_id), json.dumps({"turn_id": turn_id}), ex=_CHOICE_TTL)


async def offer_faq_choice(user: str, chat_id: str, choice: PendingFaqChoice) -> bool:
    offered = await get_async_redis_client().eval(
        """
        local raw = redis.call('GET', KEYS[1])
        if not raw or cjson.decode(raw).turn_id ~= ARGV[1] then
            return false
        end
        return redis.call('SET', KEYS[1], ARGV[2], 'EX', ARGV[3])
        """,
        1,
        _key(user, chat_id),
        choice.turn_id,
        json.dumps(asdict(choice), ensure_ascii=False),
        _CHOICE_TTL,
    )
    return bool(offered)


async def pending_faq_turn(user: str, chat_id: str) -> str | None:
    value = await get_async_redis_client().get(_key(user, chat_id))
    choice = json.loads(value) if value else {}
    return choice["turn_id"] if "answer" in choice else None


async def consume_faq_choice(user: str, chat_id: str, turn_id: str | None) -> PendingFaqChoice | None:
    if not turn_id:
        return None
    client = get_async_redis_client()
    key = _key(user, chat_id)
    value = await client.eval(
        """
        local raw = redis.call('GET', KEYS[1])
        if not raw then
            return false
        end
        local choice = cjson.decode(raw)
        if choice.turn_id ~= ARGV[1] or choice.answer == nil then
            return false
        end
        redis.call('DEL', KEYS[1])
        return raw
        """,
        1,
        key,
        turn_id,
    )
    if not value:
        return None
    saved = json.loads(value)
    return PendingFaqChoice(turn_id=saved["turn_id"], query=saved["query"], answer=saved["answer"])
