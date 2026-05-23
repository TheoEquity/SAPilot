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
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useForm } from 'react-hook-form';
import { useTranslations } from 'next-intl';
import { toast } from 'sonner';
import * as z from 'zod';
import { normalizeOrchestration, updateBotOrchestration } from '../bot-config-updater';
import { FlowCanvasEditor } from '../flow-canvas-editor';
import { FlowJsonEditor } from '../flow-json-editor';
import { normalizeFlowSchema } from '../flow-utils';
import { apiClient } from '@/lib/api/client';
import { LlmProviderModel } from '@/api';

const skillSchema = z.object({
  id: z.string().min(1),
  name: z.string().min(1),
  description: z.string(),
  enabled: z.boolean(),
  is_fallback: z.boolean(),
  type: z.enum(['llm', 'tool', 'workflow', 'hybrid']),
  provider: z.string(),
  model: z.string(),
  temperature: z.coerce.number().min(0).max(2),
  max_tokens: z.coerce.number().min(1),
  skill_prompt: z.string(),
  collections: z.array(z.object({ id: z.string() })).optional(),
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

  const [collections, setCollections] = useState<
    { id?: string; title?: string }[]
  >([]);

  const loadCollections = useCallback(async () => {
    const res = await apiClient.defaultApi.collectionsGet();
    setCollections(res.data.items || []);
  }, []);

  const defaultValues = useMemo(
    () => ({
      id: existingSkill?.id || '',
      name: existingSkill?.name || '',
      description: existingSkill?.description || '',
      enabled: existingSkill?.enabled ?? true,
      is_fallback: orchestration.intent_router?.fallback_skill_id === skillId,
      type: existingSkill?.type || 'workflow',
      provider: existingSkill?.runtime?.provider || '',
      model: existingSkill?.runtime?.model || '',
      temperature: existingSkill?.runtime?.temperature ?? 0.7,
      max_tokens: existingSkill?.runtime?.max_tokens ?? 2048,
      skill_prompt: existingSkill?.prompts?.skill_prompt || '',
      collections: existingSkill?.collections || [],
    }),
    [existingSkill],
  );
  const [flowDraft, setFlowDraft] = useState(() =>
    normalizeFlowSchema(existingSkill?.flow),
  );

  useEffect(() => {
    loadCollections();
  }, [loadCollections]);

  const [completionModels, setCompletionModels] = useState<LlmProviderModel[]>([]);
  const [selectedProvider, setSelectedProvider] = useState('');

  const uniqueProviders = useMemo(
    () => [...new Set(completionModels.map((m) => m.provider_name))],
    [completionModels],
  );

  const availableModels = useMemo(
    () => completionModels.filter((m) => m.provider_name === selectedProvider),
    [completionModels, selectedProvider],
  );

  const fetchCompletionModels = useCallback(async () => {
    try {
      const res = await apiClient.defaultApi.availableModelsPost({
        tagFilterRequest: {
          tag_filters: [{ operation: 'AND', tags: ['enable_for_agent'] }],
        },
      });
      const items = res.data.items || [];
      const models = items.flatMap((item) =>
        (item.completion || []).map((model) => ({
          ...model,
          provider_name: item.name,
          api: 'completion' as const,
        })),
      );
      setCompletionModels(models);
    } catch (error) {
      console.error('Failed to fetch available models', error);
    }
  }, []);

  useEffect(() => {
    fetchCompletionModels();
  }, [fetchCompletionModels]);

  useEffect(() => {
    if (existingSkill?.runtime?.provider) {
      setSelectedProvider(existingSkill.runtime.provider);
    }
  }, [existingSkill?.runtime?.provider]);

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
    // Check for unique default skill constraint
    if (values.is_fallback) {
      const existingFallback = orchestration.intent_router?.fallback_skill_id;
      if (existingFallback && existingFallback !== skillId) {
        toast.error(page_bot('error'), page_bot('only_one_fallback_skill_error'));
        return;
      }
    }

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
        skill_prompt: values.skill_prompt,
      },
      is_fallback: values.is_fallback,
      tools: existingSkill?.tools || [],
      io: existingSkill?.io || {
        input_schema: {},
        output_schema: {},
                  },
      flow: flowDraft,
      collections: values.collections || [],
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

      const currentFallback = orchestration.intent_router?.fallback_skill_id || '';
      const nextFallbackSkillId = values.is_fallback
        ? values.id
        : (currentFallback === skillId ? '' : currentFallback);

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
                    <FormLabel>{page_bot('skill_id')}</FormLabel>
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
                    <FormLabel>{page_bot('skill_type')}</FormLabel>
                    <Select onValueChange={field.onChange} value={field.value}>
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        <SelectItem value="workflow">{page_bot('skill_type_workflow')}</SelectItem>
                        <SelectItem value="hybrid">{page_bot('skill_type_hybrid')}</SelectItem>
                        <SelectItem value="llm">{page_bot('skill_type_llm')}</SelectItem>
                        <SelectItem value="tool">{page_bot('skill_type_tool')}</SelectItem>
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
                    <FormLabel>{page_bot('skill_enabled')}</FormLabel>
                    <FormControl>
                      <Switch checked={field.value} onCheckedChange={field.onChange} />
                    </FormControl>
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="is_fallback"
                render={({ field }) => (
                  <FormItem className="flex flex-row items-center justify-between rounded-lg border p-4">
                    <div>
                      <FormLabel>{page_bot('skill_default')}</FormLabel>
                      <p className="text-xs text-muted-foreground">{page_bot('skill_default_desc')}</p>
                    </div>
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
                    <FormLabel>{page_bot('llm_provider')}</FormLabel>
                    <Select
                      onValueChange={(val) => {
                        field.onChange(val);
                        setSelectedProvider(val);
                      }}
                      value={field.value || ''}
                      disabled={uniqueProviders.length === 0}
                    >
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder={page_bot('select_provider')} />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {uniqueProviders.map((p) => (
                          <SelectItem key={p} value={p}>{p}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="model"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{page_bot('llm_model')}</FormLabel>
                    <Select
                      onValueChange={field.onChange}
                      value={field.value || ''}
                      disabled={availableModels.length === 0}
                    >
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder={page_bot('select_model')} />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {availableModels.map((m) => (
                          <SelectItem key={m.model} value={m.model}>{m.model}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
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
              name="collections"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{page_bot('collection')}</FormLabel>
                  <FormControl>
                    <Select
                      onValueChange={(val) => {
                        const current = field.value || [];
                        if (val === '__clear__') {
                          form.setValue('collections', []);
                        } else if (!current.some((c) => c.id === val)) {
                          form.setValue('collections', [
                            ...current,
                            { id: val },
                          ]);
                        }
                      }}
                      value=""
                    >
                      <SelectTrigger className="w-full md:w-6/12">
                        <SelectValue placeholder={page_bot('collection_placeholder')} />
                      </SelectTrigger>
                      <SelectContent>
                        {collections.map((collection) => (
                          <SelectItem key={collection.id} value={collection.id || ''}>
                            {collection.title}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </FormControl>
                  {field.value && field.value.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-2">
                      {field.value.map((c) => {
                        const col = collections.find(
                          (col) => col.id === c.id,
                        );
                        return (
                          <span
                            key={c.id}
                            className="inline-flex items-center gap-1 rounded-md bg-secondary px-2 py-1 text-sm"
                          >
                            {col?.title || c.id}
                            <button
                              type="button"
                              className="ml-1 rounded-full hover:bg-accent"
                              onClick={() => {
                                form.setValue(
                                  'collections',
                                  field.value?.filter(
                                    (item) => item.id !== c.id,
                                  ) || [],
                                );
                              }}
                            >
                              ×
                            </button>
                          </span>
                        );
                      })}
                    </div>
                  )}
                </FormItem>
              )}
            />

              <FormField
                control={form.control}
                name="skill_prompt"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{page_bot('skill_prompt_label')}</FormLabel>
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
