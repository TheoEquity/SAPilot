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

from typing import Any, Optional

from pydantic import BaseModel


class ReactFlowViewport(BaseModel):
    x: float
    y: float
    zoom: float


class ReactFlowNode(BaseModel):
    id: str
    type: str
    position: dict[str, float]
    data: dict[str, Any]


class ReactFlowEdge(BaseModel):
    id: str
    source: str
    target: str
    sourceHandle: Optional[str] = None
    targetHandle: Optional[str] = None
    type: Optional[str] = None
    data: Optional[dict[str, Any]] = None


class ReactFlowSchema(BaseModel):
    version: str
    viewport: Optional[ReactFlowViewport] = None
    nodes: list[ReactFlowNode] = []
    edges: list[ReactFlowEdge] = []
