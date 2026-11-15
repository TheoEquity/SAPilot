import * as z from 'zod';
import type {
  OrchestrationConfig,
  OrchestrationSkill,
  ReactFlowSchema,
} from '../orchestration-types';

export const skillSchema = z.object({
  id: z.string().min(1),
  name: z.string().min(1),
  description: z.string(),
  enabled: z.boolean(),
  is_fallback: z.boolean(),
  type: z.enum(['llm', 'tool', 'workflow', 'hybrid']),
  category: z.string().optional(),
  provider: z.string(),
  model: z.string(),
  temperature: z.preprocess(
    (value) => (value === '' || value === null ? undefined : value),
    z.coerce.number().min(0).max(2).optional(),
  ),
  max_tokens: z.preprocess(
    (value) => (value === '' || value === null ? undefined : value),
    z.coerce.number().int().min(1).optional(),
  ),
  skill_prompt: z.string(),
  collections: z.array(z.object({ id: z.string() })).optional(),
  tools: z
    .array(z.object({ tool_id: z.string(), enabled: z.boolean() }))
    .optional(),
});

export type SkillEditorFormValues = z.output<typeof skillSchema>;

export type SkillEditorFormInput = z.input<typeof skillSchema>;

export const isRoutableSkill = (skill: OrchestrationSkill) =>
  Boolean(skill.id && skill.name && skill.category !== 'sap_faq_expansion');

const dedupeSkillsById = <T extends { id?: string }>(skills: T[]) => {
  const skillMap = new Map<string, T>();
  for (const skill of skills) {
    if (!skill.id) {
      continue;
    }
    skillMap.set(skill.id, skill);
  }
  return Array.from(skillMap.values());
};

export const buildSkillOrchestration = ({
  orchestration,
  existingSkill,
  skillId,
  values,
  flow,
  deduplicateSkills,
  updatedAt,
}: {
  orchestration: OrchestrationConfig;
  existingSkill?: OrchestrationSkill;
  skillId?: string;
  values: SkillEditorFormValues;
  flow: ReactFlowSchema;
  deduplicateSkills: boolean;
  updatedAt: string;
}): OrchestrationConfig => {
  const runtime = {
    ...existingSkill?.runtime,
    provider: values.provider || undefined,
    model: values.model || undefined,
    temperature: values.temperature,
    max_tokens: values.max_tokens,
  };
  const nextSkill: OrchestrationSkill = {
    ...existingSkill,
    id: values.id,
    name: values.name,
    description: values.description,
    enabled: values.enabled,
    type: values.type,
    category: values.category || existingSkill?.category || null,
    runtime: Object.values(runtime).some(
      (value) => value !== undefined && value !== null && value !== '',
    )
      ? runtime
      : null,
    prompts: {
      ...existingSkill?.prompts,
      skill_prompt: values.skill_prompt,
    },
    tools: (values.tools || []).map((tool) => ({
      ...existingSkill?.tools?.find(
        (binding) => binding.tool_id === tool.tool_id,
      ),
      ...tool,
    })),
    io: existingSkill?.io || {
      input_schema: {},
      output_schema: {},
    },
    flow,
    collections: values.collections || [],
    meta: {
      ...(existingSkill?.meta || {}),
      updated_at: updatedAt,
    },
  };

  const currentSkills = orchestration.skills || [];
  const updatedSkills = existingSkill
    ? currentSkills.map((skill) =>
        skill.id === existingSkill.id ? nextSkill : skill,
      )
    : [...currentSkills, nextSkill];
  const nextSkills = deduplicateSkills
    ? dedupeSkillsById(updatedSkills)
    : updatedSkills;

  const nextCandidateSkills = nextSkills
    .filter(isRoutableSkill)
    .map((skill) => {
      const existingCandidate =
        orchestration.intent_router?.candidate_skills?.find(
          (candidate) => candidate.skill_id === skill.id,
        );

      return {
        skill_id: skill.id,
        label: skill.name,
        description: skill.description,
        enabled: existingCandidate?.enabled ?? skill.enabled ?? true,
        examples: existingCandidate?.examples || [],
      };
    });

  const currentFallback = orchestration.intent_router?.fallback_skill_id || '';
  const nextFallbackSkillId =
    values.is_fallback && values.category !== 'sap_faq_expansion'
      ? values.id
      : currentFallback === skillId
        ? ''
        : currentFallback;

  return {
    ...orchestration,
    skills: nextSkills,
    intent_router: orchestration.intent_router
      ? {
          ...orchestration.intent_router,
          fallback_skill_id: nextFallbackSkillId,
          candidate_skills: nextCandidateSkills,
        }
      : orchestration.intent_router,
  };
};
