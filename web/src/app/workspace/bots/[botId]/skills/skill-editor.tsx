'use client';

import { useBotConfigContext } from '@/components/providers/bot-config-provider';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Form, FormControl, FormField, FormItem, FormLabel } from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { Textarea } from '@/components/ui/textarea';
import { zodResolver } from '@hookform/resolvers/zod';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useMemo, useState } from 'react';
import { useForm } from 'react-hook-form';
import { useTranslations } from 'next-intl';
import { toast } from 'sonner';
import * as z from 'zod';
import { normalizeOrchestration, updateBotOrchestration } from '../bot-config-updater';
import { FlowCanvasEditor } from '../flow-canvas-editor';
import { FlowJsonEditor } from '../flow-json-editor';
import { normalizeFlowSchema } from '../flow-utils';

const skillSchema = z.object({
  id: z.string().min(1),
  name: z.string().min(1),
  description: z.string(),
  enabled: z.boolean(),
  type: z.enum(['llm', 'tool', 'workflow', 'hybrid']),
  provider: z.string(),
  model: z.string(),
  temperature: z.coerce.number().min(0).max(2),
  max_tokens: z.coerce.number().min(1),
  system_prompt: z.string(),
  query_prompt: z.string(),
  skill_prompt: z.string(),
});

type SkillEditorFormValues = z.output<typeof skillSchema>;

export const SkillEditor = ({ skillId }: { skillId?: string }) => {
  const { bot, loadBot } = useBotConfigContext();
  const page_bot = useTranslations('page_bot');
  const common_tips = useTranslations('common.tips');
  const router = useRouter();

  const orchestration = normalizeOrchestration(bot);
  const existingSkill = useMemo(
    () => orchestration.skills?.find((skill) => skill.id === skillId),
    [orchestration.skills, skillId],
  );

  const defaultValues = useMemo(
    () => ({
      id: existingSkill?.id || '',
      name: existingSkill?.name || '',
      description: existingSkill?.description || '',
      enabled: existingSkill?.enabled ?? true,
      type: existingSkill?.type || 'workflow',
      provider: existingSkill?.runtime?.provider || '',
      model: existingSkill?.runtime?.model || '',
      temperature: existingSkill?.runtime?.temperature ?? 0.7,
      max_tokens: existingSkill?.runtime?.max_tokens ?? 2048,
      system_prompt: existingSkill?.prompts?.system_prompt || '',
      query_prompt: existingSkill?.prompts?.query_prompt || '',
      skill_prompt: existingSkill?.prompts?.skill_prompt || '',
    }),
    [existingSkill],
  );
  const [flowDraft, setFlowDraft] = useState(() =>
    normalizeFlowSchema(existingSkill?.flow),
  );

  const form = useForm<
    z.input<typeof skillSchema>,
    undefined,
    z.output<typeof skillSchema>
  >({
    resolver: zodResolver(skillSchema),
    defaultValues,
  });

  useEffect(() => {
    form.reset(defaultValues);
  }, [defaultValues, form]);

  useEffect(() => {
    setFlowDraft(normalizeFlowSchema(existingSkill?.flow));
  }, [existingSkill?.flow]);

  const handleSave = form.handleSubmit(async (values) => {
    const nextSkill = {
      id: values.id,
      name: values.name,
      description: values.description,
      enabled: values.enabled,
      type: values.type,
      runtime: {
        provider: values.provider,
        model: values.model,
        temperature: values.temperature,
        max_tokens: values.max_tokens,
      },
      prompts: {
        system_prompt: values.system_prompt,
        query_prompt: values.query_prompt,
        skill_prompt: values.skill_prompt,
      },
      tools: existingSkill?.tools || [],
      io: existingSkill?.io || {
        input_schema: {},
        output_schema: {},
                  },
      flow: flowDraft,
      meta: {
        ...(existingSkill?.meta || {}),
        updated_at: new Date().toISOString(),
      },
    };

    const currentSkills = orchestration.skills || [];
    const nextSkills = existingSkill
      ? currentSkills.map((skill) =>
          skill.id === existingSkill.id ? nextSkill : skill,
        )
      : [...currentSkills, nextSkill];

    const nextCandidateSkills = nextSkills
      .filter((skill) => skill.id && skill.name)
      .map((skill) => {
        const existingCandidate = orchestration.intent_router?.candidate_skills?.find(
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

    const nextFallbackSkillId =
      orchestration.intent_router?.fallback_skill_id &&
      nextSkills.some(
        (skill) => skill.id === orchestration.intent_router?.fallback_skill_id,
      )
        ? orchestration.intent_router.fallback_skill_id
        : nextSkills[0]?.id || '';

    await updateBotOrchestration({
      bot,
      orchestration: {
        ...orchestration,
        skills: nextSkills,
        intent_router: orchestration.intent_router
          ? {
              ...orchestration.intent_router,
              fallback_skill_id: nextFallbackSkillId,
              candidate_skills: nextCandidateSkills,
            }
          : orchestration.intent_router,
      },
    });

    await loadBot();
    toast.success(common_tips('update_success'));
    router.push(`/workspace/bots/${bot.id}/skills`);
    router.refresh();
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>{existingSkill ? existingSkill.name : page_bot('new_skill')}</CardTitle>
        <CardDescription>{page_bot('skills_description')}</CardDescription>
      </CardHeader>
      <CardContent>
        <Form {...form}>
          <form onSubmit={handleSave} className="flex flex-col gap-6">
            <div className="grid gap-4 md:grid-cols-2">
              <FormField
                control={form.control}
                name="id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>ID</FormLabel>
                    <FormControl>
                      <Input {...field} value={field.value || ''} />
                    </FormControl>
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{page_bot('title')}</FormLabel>
                    <FormControl>
                      <Input {...field} value={field.value || ''} />
                    </FormControl>
                  </FormItem>
                )}
              />
            </div>

            <FormField
              control={form.control}
              name="description"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{page_bot('description')}</FormLabel>
                  <FormControl>
                    <Textarea {...field} value={field.value || ''} className="h-24" />
                  </FormControl>
                </FormItem>
              )}
            />

            <div className="grid gap-4 md:grid-cols-2">
              <FormField
                control={form.control}
                name="type"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Type</FormLabel>
                    <Select onValueChange={field.onChange} value={field.value}>
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        <SelectItem value="workflow">Workflow</SelectItem>
                        <SelectItem value="hybrid">Hybrid</SelectItem>
                        <SelectItem value="llm">LLM</SelectItem>
                        <SelectItem value="tool">Tool</SelectItem>
                      </SelectContent>
                    </Select>
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="enabled"
                render={({ field }) => (
                  <FormItem className="flex flex-row items-center justify-between rounded-lg border p-4">
                    <FormLabel>{page_bot('orchestration_configured')}</FormLabel>
                    <FormControl>
                      <Switch checked={field.value} onCheckedChange={field.onChange} />
                    </FormControl>
                  </FormItem>
                )}
              />
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <FormField
                control={form.control}
                name="provider"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>LLM Provider</FormLabel>
                    <FormControl>
                      <Input {...field} value={field.value || ''} />
                    </FormControl>
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="model"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>LLM Model</FormLabel>
                    <FormControl>
                      <Input {...field} value={field.value || ''} />
                    </FormControl>
                  </FormItem>
                )}
              />
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <FormField
                control={form.control}
                name="temperature"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Temperature</FormLabel>
                    <FormControl>
                      <Input
                        type="number"
                        step="0.1"
                        {...field}
                        value={typeof field.value === 'number' ? field.value : ''}
                      />
                    </FormControl>
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="max_tokens"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Max Tokens</FormLabel>
                    <FormControl>
                      <Input
                        type="number"
                        {...field}
                        value={typeof field.value === 'number' ? field.value : ''}
                      />
                    </FormControl>
                  </FormItem>
                )}
              />
            </div>

            <FormField
              control={form.control}
              name="system_prompt"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{page_bot('system_prompt_template')}</FormLabel>
                  <FormControl>
                    <Textarea {...field} value={field.value || ''} className="h-32 font-mono text-sm" />
                  </FormControl>
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="query_prompt"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{page_bot('query_prompt_template')}</FormLabel>
                  <FormControl>
                    <Textarea {...field} value={field.value || ''} className="h-24 font-mono text-sm" />
                  </FormControl>
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="skill_prompt"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{page_bot('skills_title')}</FormLabel>
                  <FormControl>
                    <Textarea {...field} value={field.value || ''} className="h-24 font-mono text-sm" />
                  </FormControl>
                </FormItem>
                )}
              />

            <FlowCanvasEditor
              title={page_bot('skill_flow_canvas_title')}
              description={page_bot('skill_flow_canvas_description')}
              value={flowDraft}
              onChange={setFlowDraft}
              skillOptions={(orchestration.skills || []).map((skill) => ({
                id: skill.id,
                label: skill.name,
              }))}
            />

            <FlowJsonEditor
              title={page_bot('skill_flow_title')}
              description={page_bot('skill_flow_description')}
              value={flowDraft}
              onChange={setFlowDraft}
            />

            <div className="flex gap-3">
              <Button variant="outline" asChild>
                <Link href={`/workspace/bots/${bot.id}/skills`}>
                  {page_bot('cancel')}
                </Link>
              </Button>
              <Button type="submit">{page_bot('save_settings')}</Button>
            </div>
          </form>
        </Form>
      </CardContent>
    </Card>
  );
};
