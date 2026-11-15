"""Apply SAP scenario Skills to the existing Default Agent."""

import argparse
import asyncio
import json

from aperag.db.ops import async_db_ops
from aperag.schema import view_models as models
from aperag.service.bot_service import BotService
from aperag.service.sap_bot_configuration import configure_knowledge_bot


async def configure(args) -> None:
    service = BotService()
    bot = await service.get_bot(args.user, args.bot)
    config = bot.config
    if not bot.is_default or bot.type != "agent" or not config or not config.agent or not config.agent.completion:
        raise ValueError("Select the existing Default Agent with a completion model")
    if not config.orchestration or not config.orchestration.intent_router:
        raise ValueError("The selected Bot needs an intent router")
    if not await async_db_ops.query_collection(args.user, args.tcode_collection):
        raise ValueError("The transaction-code collection is not owned by the selected user")
    knowledge = configure_knowledge_bot(
        config,
        args.tcode_collection,
        faq_skill_id=args.faq_skill,
        policy_skill_id=args.policy_skill,
        technical_skill_id=args.technical_skill,
        retired_code_skill_id=args.old_code_skill,
        technical_external_tools=tuple(args.technical_tool),
        faq_external_tools=tuple(args.faq_tool),
    )
    if args.apply:
        await service.update_bot(args.user, args.bot, models.BotUpdate(config=knowledge))
    print(json.dumps({
        "default_agent": args.bot,
        "skills": [skill.name for skill in knowledge.orchestration.skills],
        "applied": args.apply,
    }, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user", required=True)
    parser.add_argument("--bot", required=True)
    parser.add_argument("--tcode-collection", required=True)
    parser.add_argument("--faq-skill", default="sap_faq")
    parser.add_argument("--policy-skill", default="ops_policy")
    parser.add_argument("--technical-skill", default="sap_knowledge")
    parser.add_argument("--old-code-skill", default="abap_reader")
    parser.add_argument("--technical-tool", action="append", default=[])
    parser.add_argument("--faq-tool", action="append", default=[])
    parser.add_argument("--apply", action="store_true")
    asyncio.run(configure(parser.parse_args()))


if __name__ == "__main__":
    main()
