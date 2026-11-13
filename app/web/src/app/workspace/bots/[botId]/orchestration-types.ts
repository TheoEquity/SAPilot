import type {
  ReactFlowEdge as ApiReactFlowEdge,
  ReactFlowNode as ApiReactFlowNode,
  ReactFlowSchema as ApiReactFlowSchema,
  BotConfigInput,
  BotConfigOutput,
} from '@/api/generated/models';

export type {
  CandidateSkill,
  IntentRouterLLMConfig,
  IntentRouterRule,
  OrchestrationConfigOutput as OrchestrationConfig,
  SkillConfigOutput as OrchestrationSkill,
  ReactFlowViewport,
  SkillCollection,
  SkillIOConfig,
  SkillPrompts,
  SkillRuntimeConfig,
  SkillToolBinding,
} from '@/api/generated/models';

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

export type BotConfigWithOrchestration = BotConfigOutput;

export const toBotConfigInput = (config: BotConfigOutput): BotConfigInput => ({
  agent: config.agent,
  flow: config.flow,
  orchestration: config.orchestration,
});
