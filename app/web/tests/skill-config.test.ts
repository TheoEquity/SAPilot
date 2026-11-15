import assert from 'node:assert/strict';
import test from 'node:test';
import type {
  OrchestrationConfig,
  ReactFlowSchema,
} from '../src/app/workspace/bots/[botId]/orchestration-types';
import {
  buildSkillOrchestration,
  skillSchema,
} from '../src/app/workspace/bots/[botId]/skills/skill-config';

const flow = { version: '1', nodes: [], edges: [] } as ReactFlowSchema;
const existingSkill = {
  id: 'code_explain',
  name: '代码解读',
  category: 'sap_code',
  runtime: null,
};
const orchestration = {
  skills: [
    existingSkill,
    {
      id: 'faq_followup',
      name: 'FAQ 专业扩展',
      category: 'sap_faq_expansion',
    },
  ],
  intent_router: {
    id: 'main',
    name: '主意图识别器',
    prompt_template: '',
    llm: { provider: '', model: '' },
    fallback_skill_id: 'code_explain',
    candidate_skills: [
      {
        skill_id: 'code_explain',
        label: '代码解读',
        enabled: true,
        examples: [],
      },
    ],
  },
} as OrchestrationConfig;

test('empty runtime fields keep inherited runtime and FAQ expansion stays outside normal routing', () => {
  const values = skillSchema.parse({
    id: 'code_explain',
    name: '代码解读',
    description: '',
    enabled: true,
    is_fallback: false,
    type: 'workflow',
    provider: '',
    model: '',
    temperature: '',
    max_tokens: '',
    skill_prompt: '',
    collections: [],
    tools: [],
  });
  const result = buildSkillOrchestration({
    orchestration,
    existingSkill,
    skillId: 'code_explain',
    values,
    flow,
    deduplicateSkills: true,
    updatedAt: '2026-11-14T00:00:00Z',
  });

  assert.equal(result.skills?.[0].runtime, null);
  assert.deepEqual(
    result.intent_router?.candidate_skills?.map((item) => item.skill_id),
    ['code_explain'],
  );
});

test('explicit runtime overrides remain saved', () => {
  const values = skillSchema.parse({
    id: 'code_explain',
    name: '代码解读',
    description: '',
    enabled: true,
    is_fallback: false,
    type: 'workflow',
    provider: 'provider',
    model: 'model',
    temperature: '0.2',
    max_tokens: '4096',
    skill_prompt: '',
    collections: [],
    tools: [],
  });
  const result = buildSkillOrchestration({
    orchestration,
    existingSkill,
    skillId: 'code_explain',
    values,
    flow,
    deduplicateSkills: true,
    updatedAt: '2026-11-14T00:00:00Z',
  });

  assert.equal(result.skills?.[0].runtime?.max_tokens, 4096);
  assert.equal(result.skills?.[0].runtime?.temperature, 0.2);
});

test('FAQ expansion cannot become the fallback skill', () => {
  const values = skillSchema.parse({
    id: 'faq_followup',
    name: 'FAQ 专业扩展',
    description: '',
    enabled: true,
    is_fallback: true,
    type: 'workflow',
    category: 'sap_faq_expansion',
    provider: '',
    model: '',
    temperature: '',
    max_tokens: '',
    skill_prompt: '',
    collections: [],
    tools: [],
  });
  const result = buildSkillOrchestration({
    orchestration,
    existingSkill: orchestration.skills?.[1],
    skillId: 'faq_followup',
    values,
    flow,
    deduplicateSkills: true,
    updatedAt: '2026-11-14T00:00:00Z',
  });

  assert.equal(result.intent_router?.fallback_skill_id, 'code_explain');
  assert.deepEqual(
    result.intent_router?.candidate_skills?.map((item) => item.skill_id),
    ['code_explain'],
  );
});
