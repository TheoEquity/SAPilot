import type { IntentRouterLLMConfig } from '../../web/src/api/generated/models/intentRouterLLMConfig';
import type { SkillRuntimeConfig } from '../../web/src/api/generated/models/skillRuntimeConfig';
import type { CandidateSkill } from '../../web/src/api/generated/models/candidateSkill';
import type { BotUpdate } from '../../web/src/api/generated/models/botUpdate';

const runtime: SkillRuntimeConfig = {
  temperature: null,
  max_tokens: null,
  top_p: null,
  timeout_ms: null,
};
const candidate: CandidateSkill = { skill_id: 'one', label: 'one', examples: null };
const update: BotUpdate = { is_default: null, is_protected: false, config: { orchestration: null } };
const intent: IntentRouterLLMConfig = { provider: 'test', model: 'test' };
// Existing non-null default fields must not become nullable during generation.
// @ts-expect-error temperature on IntentRouterLLMConfig does not accept null
const invalidIntent: IntentRouterLLMConfig = { provider: 'test', model: 'test', temperature: null };
void [runtime, candidate, update, intent, invalidIntent];
