import type { BotConfig } from '@/api/models/bot-config';

export type IntentRouterLLMConfig = {
  provider?: string;
  model?: string;
  temperature?: number;
  max_tokens?: number;
  top_p?: number;
  timeout_ms?: number;
};

export type CandidateSkill = {
  skill_id: string;
  label: string;
  description?: string;
  enabled?: boolean;
  examples?: string[];
};

export type IntentRouterRule = {
  rule_type: 'keyword' | 'regex';
  value: string;
  target_skill_id: string;
  enabled?: boolean;
  description?: string;
};

export type ReactFlowViewport = {
  x: number;
  y: number;
  zoom: number;
};

export type ReactFlowNode = {
  id: string;
  type: string;
  position: { x: number; y: number };
  data: Record<string, unknown>;
};

export type ReactFlowEdge = {
  id: string;
  source: string;
  target: string;
  sourceHandle?: string;
  targetHandle?: string;
  type?: string;
  data?: Record<string, unknown>;
};

export type ReactFlowSchema = {
  version: string;
  viewport?: ReactFlowViewport;
  nodes: ReactFlowNode[];
  edges: ReactFlowEdge[];
};

type OrchestrationIntentRouter = {
  id?: string;
  name?: string;
  description?: string;
  enabled?: boolean;
  mode?: 'llm' | 'rules+llm';
  llm?: IntentRouterLLMConfig;
  prompt_template?: string;
  confidence_threshold?: number;
  fallback_skill_id?: string;
  candidate_skills?: CandidateSkill[];
  rules?: IntentRouterRule[];
  flow?: ReactFlowSchema;
  meta?: Record<string, unknown>;
};

export type MCPToolInfo = {
  name: string;
  description: string;
};

export type SkillToolBinding = {
  tool_id: string;
  enabled?: boolean;
  required?: boolean;
  timeout_ms?: number;
  retry_count?: number;
};

export type SkillRuntimeConfig = {
  provider?: string;
  model?: string;
  temperature?: number;
  max_tokens?: number;
  top_p?: number;
  timeout_ms?: number;
};

export type SkillPrompts = {
  skill_prompt?: string;
};

export type SkillIOConfig = {
  input_schema?: Record<string, unknown>;
  output_schema?: Record<string, unknown>;
};

export type SkillCollection = {
  id: string;
};

export type OrchestrationSkill = {
  id: string;
  name: string;
  description?: string;
  enabled?: boolean;
  type?: 'llm' | 'tool' | 'workflow' | 'hybrid';
  category?: string;
  runtime?: SkillRuntimeConfig;
  prompts?: SkillPrompts;
  tools?: SkillToolBinding[];
  io?: SkillIOConfig;
  flow?: ReactFlowSchema;
  collections?: SkillCollection[];
  meta?: Record<string, unknown>;
};

export type OrchestrationConfig = {
  intent_router?: OrchestrationIntentRouter;
  skills?: OrchestrationSkill[];
};

export type BotConfigWithOrchestration = BotConfig & {
  orchestration?: OrchestrationConfig;
};
