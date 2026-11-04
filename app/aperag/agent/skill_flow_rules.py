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

import logging
from typing import Any, Optional

from aperag.schema.skill_flow import ReactFlowNode
from aperag.schema.view_models import SkillConfig

logger = logging.getLogger(__name__)


def get_flow_start_node_id(skill_config: SkillConfig) -> Optional[str]:
    if not skill_config.flow or not skill_config.flow.nodes:
        return None

    nodes = skill_config.flow.nodes
    incoming_count = {node.id: 0 for node in nodes}
    for edge in skill_config.flow.edges:
        if edge.target in incoming_count and edge.source != edge.target:
            incoming_count[edge.target] += 1

    explicit_start = next(
        (
            node.id
            for node in nodes
            if node.type == "startEnd"
            and str(node.data.get("label", "")).strip().lower() in {"start", "开始"}
        ),
        None,
    )
    if explicit_start:
        return explicit_start

    zero_incoming = [node.id for node in nodes if incoming_count.get(node.id, 0) == 0]
    if zero_incoming:
        return zero_incoming[0]

    return nodes[0].id

def _normalize_condition_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return ""
    normalized = str(value).strip().lower()
    if normalized in {"yes", "y", "1"}:
        return "true"
    if normalized in {"no", "n", "0"}:
        return "false"
    return normalized

def evaluate_condition_node(
    node: ReactFlowNode,
    node_results: dict[str, dict[str, Any]],
) -> str:
    source_node_id = str(node.data.get("source_node_id") or "").strip()
    field = str(node.data.get("field") or "").strip()
    operator = str(node.data.get("operator") or "equals").strip().lower()
    expected_value = _normalize_condition_value(node.data.get("expected_value"))

    source_result = node_results.get(source_node_id, {})
    outputs = source_result.get("outputs", {}) if isinstance(source_result, dict) else {}
    actual_value = outputs.get(field) if isinstance(outputs, dict) else None
    normalized_actual = _normalize_condition_value(actual_value)

    matched = False
    if operator == "exists":
        matched = field in outputs if isinstance(outputs, dict) else False
    elif operator == "not_equals":
        matched = normalized_actual != expected_value
    else:
        matched = normalized_actual == expected_value

    decision = "yes" if matched else "no"
    logger.info(
        "Condition node %s evaluated: source=%s field=%s operator=%s actual=%s expected=%s decision=%s",
        node.id,
        source_node_id,
        field,
        operator,
        normalized_actual,
        expected_value,
        decision,
    )
    return decision
