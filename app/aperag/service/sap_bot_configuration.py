"""Configure SAP scenarios using the existing Bot and Skill models."""

from aperag.agent.sap_scenarios import (
    CODE_SCENARIO,
    EXTERNAL_TOOLS,
    FAQ_EXPANSION,
    FAQ_SCENARIO,
    GENERAL_SCENARIO,
    POLICY_SCENARIO,
    TCODE_SCENARIO,
    TECHNICAL_SCENARIO,
)
from aperag.schema import skill_flow
from aperag.schema import view_models as models


def _skill(skill_id: str, title: str, category: str, prompt: str, tools=(), collections=()) -> models.SkillConfig:
    return models.SkillConfig(
        id=skill_id,
        name=title,
        category=category,
        description=prompt,
        type="llm",
        prompts=models.SkillPrompts(skill_prompt=prompt),
        tools=[models.SkillToolBinding(tool_id=tool, enabled=True) for tool in tools],
        collections=[models.SkillCollection(id=collection_id) for collection_id in collections],
        flow=skill_flow.ReactFlowSchema(
            version="1.0",
            nodes=[
                skill_flow.ReactFlowNode(id="answer", type="action", position={"x": 0, "y": 0}, data={"label": title})
            ],
        ),
    )


def _candidate(skill: models.SkillConfig) -> models.CandidateSkill:
    return models.CandidateSkill(skill_id=skill.id, label=skill.name, description=skill.description)


def _code_skills() -> list[models.SkillConfig]:
    return [
        _skill(
            "code_explain", "代码解读", CODE_SCENARIO, "说明代码用途、输入输出和处理过程。按语言解释关键语句和分支。"
        ),
        _skill(
            "code_standards",
            "代码规范检查",
            CODE_SCENARIO,
            "检查 ABAP 或 Java 代码。优先采用用户明确提供的规范和版本，逐条标明代码位置和依据。没有项目规范时，明确标注为通用建议。",
        ),
        _skill(
            "code_suggestions",
            "修改建议",
            CODE_SCENARIO,
            "解释问题、建议的改法和影响。按需给出供用户审阅的示例，并标明需要用户验证的假设。",
        ),
    ]


def configure_knowledge_bot(
    config: models.BotConfig,
    tcode_collection_id: str,
    *,
    faq_skill_id: str,
    policy_skill_id: str,
    technical_skill_id: str,
    retired_code_skill_id: str,
    technical_external_tools: tuple[str, ...] = (),
    faq_external_tools: tuple[str, ...] = (),
) -> models.BotConfig:
    if not set(technical_external_tools + faq_external_tools) <= EXTERNAL_TOOLS:
        raise ValueError("Only supported external tools may be configured")
    updated = config.model_copy(deep=True)
    if not updated.orchestration or not updated.orchestration.intent_router:
        raise ValueError("The knowledge Bot requires an existing intent router")
    orchestration = updated.orchestration
    router = orchestration.intent_router
    by_id = {skill.id: skill for skill in orchestration.skills}
    faq, policy, technical = (by_id[skill_id] for skill_id in (faq_skill_id, policy_skill_id, technical_skill_id))
    for skill in (faq, policy):
        if not skill.collections:
            raise ValueError(f"{skill.name} requires an approved collection")
    faq.category = FAQ_SCENARIO
    faq.prompts = models.SkillPrompts(
        skill_prompt="按 FAQ 原文说明问题和处理步骤并引用出处。找不到直接依据时说明未匹配。"
    )
    policy.category = POLICY_SCENARIO
    policy.prompts = models.SkillPrompts(
        skill_prompt="只按当前问题适用的规范原文作答，逐条给出出处。不适用或没有条款时说明缺少依据。"
    )
    technical.category = TECHNICAL_SCENARIO
    technical.prompts = models.SkillPrompts(
        skill_prompt="解释 SAP 功能、消息号及原理。允许直接回答。仅在启用相应工具且确有需要时查询 SAP Help 或其他获准外部来源。"
    )
    technical.tools = [
        models.SkillToolBinding(tool_id=name, enabled=True) for name in ("search_collection", *technical_external_tools)
    ]
    technical.flow = _skill(technical.id, technical.name, TECHNICAL_SCENARIO, "").flow
    expansion = _skill(
        "faq_followup", "FAQ 专业扩展", FAQ_EXPANSION, "根据用户确认和原问题提供补充分析。", faq_external_tools
    )
    tcode = _skill(
        "transaction_lookup",
        "事务码查询",
        TCODE_SCENARIO,
        "已给出完整事务码时查询其用途，按操作目的询问可用事务码时倒查多个条目。",
        collections=[tcode_collection_id],
    )
    code_skills = _code_skills()
    replaced = {expansion.id, tcode.id, retired_code_skill_id, *(skill.id for skill in code_skills)}
    orchestration.skills = [skill for skill in orchestration.skills if skill.id not in replaced] + [
        expansion, tcode, *code_skills,
    ]
    router.candidate_skills = [candidate for candidate in router.candidate_skills if candidate.skill_id not in replaced]
    router.candidate_skills.extend(_candidate(skill) for skill in [tcode, *code_skills])
    router.prompt_template = router.prompt_template.replace(retired_code_skill_id, "code_explain")
    router.prompt_template = router.prompt_template.replace(
        "检查某段代码是否符合指定规范 -> code_explain", "检查某段代码是否符合指定规范 -> code_standards"
    )
    code_routing = (
        "ABAP 和 Java：解释具体代码或源码文件选 code_explain，检查给出的代码选 code_standards，"
        "要求给出改法或修改建议选 code_suggestions。查询制度条款仍选运维规章制度检索。"
    )
    if code_routing not in router.prompt_template:
        router.prompt_template += "\n" + code_routing
    if "事务码" not in router.prompt_template:
        router.prompt_template += "\n查询完整事务码用途或按操作目的找事务码时，选择事务码查询。"
    router.rules = [rule for rule in router.rules if rule.target_skill_id not in replaced]
    if router.fallback_skill_id in replaced:
        router.fallback_skill_id = technical.id
    fallback = by_id.get(router.fallback_skill_id)
    if fallback and fallback not in (faq, policy, technical) and not fallback.collections:
        fallback.category = GENERAL_SCENARIO
        fallback.prompts = models.SkillPrompts()
        fallback.flow = _skill(fallback.id, fallback.name, GENERAL_SCENARIO, "").flow
        greeting = models.IntentRouterRule(
            rule_type="regex", target_skill_id=fallback.id,
            value=r"^\s*(?:你好|您好|早上好|下午好|晚上好|你是谁|你能做什么|hello|hi|hey|who are you)[\s！!。？?]*$",
        )
        if greeting not in router.rules:
            router.rules.insert(0, greeting)
        router.mode = "rules+llm"
    return updated
