"""Apply the Code Agent and SAP scenario configuration to an existing local Bot."""

import argparse
import asyncio
import json

from aperag.db.ops import async_db_ops
from aperag.schema import view_models as models
from aperag.service.bot_service import BotService
from aperag.service.sap_bot_configuration import build_code_bot, configure_knowledge_bot


async def configure(args) -> None:
    service = BotService()
    bot = await service.get_bot(args.user, args.bot)
    config = bot.config
    if bot.type != "agent" or not config or not config.agent or not config.agent.completion:
        raise ValueError("Select an existing Agent Bot with a completion model")
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
    code = build_code_bot(config.agent.completion, config.orchestration.intent_router.llm)
    bots = await service.list_bots(args.user)
    existing = [candidate for candidate in bots.items or [] if candidate.title == code.title]
    if len(existing) > 1:
        raise ValueError("More than one Code Agent has the configured title")
    if existing:
        from aperag.agent.sap_scenarios import is_code_orchestration

        if not existing[0].config or not is_code_orchestration(existing[0].config.orchestration):
            raise ValueError("An unrelated Bot already uses the Code Agent title")
    if args.apply:
        code_bot = existing[0] if existing else await service.create_bot(args.user, code)
        await service.update_bot(args.user, args.bot, models.BotUpdate(config=knowledge))
        print(json.dumps({"knowledge_bot": args.bot, "code_bot": code_bot.id}))
    else:
        print(
            json.dumps(
                {
                    "knowledge_bot": args.bot,
                    "code_bot": existing[0].id if existing else None,
                    "knowledge_skills": [skill.name for skill in knowledge.orchestration.skills],
                    "code_skills": [skill.name for skill in code.config.orchestration.skills],
                },
                ensure_ascii=False,
            )
        )


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
