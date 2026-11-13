"""Execution boundaries for the configured SAP business scenarios."""

from dataclasses import dataclass
from enum import Enum
from typing import Any

CODE_SCENARIO = "sap_code"
FAQ_SCENARIO = "sap_faq"
FAQ_EXPANSION = "sap_faq_expansion"
POLICY_SCENARIO = "sap_policy"
TECHNICAL_SCENARIO = "sap_technical"
TCODE_SCENARIO = "sap_tcode"
GENERAL_SCENARIO = "sap_general"
SCOPED_SCENARIOS = frozenset(
    {
        CODE_SCENARIO,
        FAQ_SCENARIO,
        FAQ_EXPANSION,
        POLICY_SCENARIO,
        TECHNICAL_SCENARIO,
        GENERAL_SCENARIO,
    }
)
EXTERNAL_TOOLS = frozenset({"search_sap_help", "web_search", "web_read"})
COLLECTION_TOOLS = frozenset({"search_collection"})


class EvidenceStatus(str, Enum):
    MATCH = "[MATCH]"
    NO_MATCH = "[NO_MATCH]"


def ground_answer(answer: str, references: list[dict[str, Any]], missing: str) -> tuple[str, list[dict[str, Any]]]:
    """Require the answer step to identify whether its evidence directly supports the reply."""
    status, _, content = answer.strip().partition("\n")
    if status.strip() != EvidenceStatus.MATCH or not content.strip() or not references:
        return missing, []
    citation, separator, answer_text = content.strip().partition("\n")
    citation_ids = citation.removeprefix("EVIDENCE:").strip().split(",") if citation.startswith("EVIDENCE:") else []
    if not separator or not answer_text.strip() or not citation_ids:
        return missing, []
    requested = {value.strip() for value in citation_ids}
    selected = {}
    for reference in references:
        evidence_id = reference.get("evidence_id")
        if evidence_id in requested:
            selected.setdefault(evidence_id, reference)
    if selected.keys() != requested:
        return missing, []
    return answer_text.strip(), [
        {key: value for key, value in ref.items() if key != "evidence_id"} for ref in selected.values()
    ]


@dataclass(frozen=True)
class SkillToolScope:
    tools: frozenset[str]
    collections: frozenset[str] = frozenset()

    def allows(self, tool_name: str, arguments: dict[str, Any]) -> bool:
        if not tool_name.startswith("aperag_"):
            return False
        name = tool_name.removeprefix("aperag_")
        if name not in self.tools:
            return False
        if name in COLLECTION_TOOLS:
            collection_id = arguments.get("collection_id")
            return isinstance(collection_id, str) and collection_id in self.collections
        return True


def is_code_orchestration(orchestration) -> bool:
    skills = [skill for skill in orchestration.skills if skill.enabled] if orchestration else []
    return bool(skills) and all(skill.category == CODE_SCENARIO for skill in skills)
