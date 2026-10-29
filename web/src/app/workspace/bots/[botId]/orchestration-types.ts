import type { BotConfig } from '@/api/models/bot-config';
import type { ReactFlowEdge as ApiReactFlowEdge } from '@/api/models/react-flow-edge';
import type { ReactFlowNode as ApiReactFlowNode } from '@/api/models/react-flow-node';
import type { ReactFlowSchema as ApiReactFlowSchema } from '@/api/models/react-flow-schema';

export type { IntentRouterLLMConfig } from '@/api/models/intent-router-llmconfig';
export type { CandidateSkill } from '@/api/models/candidate-skill';
export type { IntentRouterRule } from '@/api/models/intent-router-rule';
export type { ReactFlowViewport } from '@/api/models/react-flow-viewport';
export type { SkillToolBinding } from '@/api/models/skill-tool-binding';
export type { SkillRuntimeConfig } from '@/api/models/skill-runtime-config';
export type { SkillPrompts } from '@/api/models/skill-prompts';
export type { SkillIOConfig } from '@/api/models/skill-ioconfig';
export type { SkillCollection } from '@/api/models/skill-collection';
export type { SkillConfig as OrchestrationSkill } from '@/api/models/skill-config';
export type { OrchestrationConfig } from '@/api/models/orchestration-config';

// The canvas works with normalized arrays and x/y coordinates; the API also accepts
// omitted arrays and arbitrary numeric position keys for existing stored flows.
export type ReactFlowNode = ApiReactFlowNode & {
  position: { x: number; y: number };
};
export type ReactFlowEdge = Omit<ApiReactFlowEdge, 'type'> & {
  type?: string;
};
export type ReactFlowSchema = ApiReactFlowSchema & {
  nodes: ReactFlowNode[];
  edges: ReactFlowEdge[];
};

export type MCPToolInfo = {
  name: string;
  description: string;
};

export type BotConfigWithOrchestration = BotConfig;
