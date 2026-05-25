'use client';

import { LlmProviderModel } from '@/api';
import { useBotConfigContext } from '@/components/providers/bot-config-provider';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
} from '@/components/ui/form';
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
import { apiClient } from '@/lib/api/client';
import { zodResolver } from '@hookform/resolvers/zod';
import { useTranslations } from 'next-intl';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useForm } from 'react-hook-form';
import { toast } from 'sonner';
import * as z from 'zod';
import {
  normalizeOrchestration,
  updateBotOrchestration,
} from '../bot-config-updater';
import { FlowCanvasEditor } from '../flow-canvas-editor';
import { FlowJsonEditor } from '../flow-json-editor';
import { normalizeFlowSchema } from '../flow-utils';
import { IntentRouterRule } from '../orchestration-types';

const intentRouterSchema = z.object({
  name: z.string().min(1),
  description: z.string(),
  enabled: z.boolean(),
  mode: z.enum(['llm', 'rules+llm']),
  fallback_skill_id: z.string(),
  confidence_threshold: z.coerce.number().min(0).max(1),
  llm_provider: z.string(),
  llm_model: z.string(),
  temperature: z.coerce.number().min(0).max(2),
  max_tokens: z.coerce.number().min(1),
  prompt_template: z.string(),
});

type IntentRouterFormValues = z.output<typeof intentRouterSchema>;

export const IntentRouterEditor = () => {
  const { bot, loadBot } = useBotConfigContext();
  const page_bot = useTranslations('page_bot');
  const common_tips = useTranslations('common.tips');
  const router = useRouter();

  const orchestration = normalizeOrchestration(bot);
  const intentRouter = orchestration.intent_router;
  const skills = useMemo(() => {
    const skillMap = new Map(
      (orchestration.skills || []).map((skill) => [skill.id, skill]),
    );
    return Array.from(skillMap.values());
  }, [orchestration.skills]);

  const skillOptions = useMemo(
    () => skills.filter((skill) => skill.id && skill.name),
    [skills],
  );

  const getRulePlaceholder = useCallback(
    (ruleType: string): string => {
      const key =
        ruleType === 'regex'
          ? 'rule_value_placeholder_regex'
          : 'rule_value_placeholder_keyword';
      return (page_bot as (key: string) => string)(key);
    },
    [page_bot],
  );

  const validFallbackSkillId = useMemo(() => {
    if (
      intentRouter?.fallback_skill_id &&
      skillOptions.some((skill) => skill.id === intentRouter.fallback_skill_id)
    ) {
      return intentRouter.fallback_skill_id;
    }

    return skillOptions[0]?.id || '';
  }, [intentRouter?.fallback_skill_id, skillOptions]);

  const candidateSkills = useMemo(
    () =>
      skillOptions.map((skill) => {
        const existingCandidate = intentRouter?.candidate_skills?.find(
          (candidate) => candidate.skill_id === skill.id,
        );

        return {
          skill_id: skill.id,
          label: skill.name,
          description: skill.description,
          enabled: existingCandidate?.enabled ?? skill.enabled ?? true,
          examples: existingCandidate?.examples || [],
        };
      }),
    [intentRouter?.candidate_skills, skillOptions],
  );

  const defaultValues = useMemo(
    () => ({
      name: intentRouter?.name || '主意图识别器',
      description: intentRouter?.description || '',
      enabled: intentRouter?.enabled ?? true,
      mode: intentRouter?.mode || 'llm',
      fallback_skill_id: validFallbackSkillId,
      confidence_threshold: intentRouter?.confidence_threshold ?? 0.6,
      llm_provider: intentRouter?.llm?.provider || '',
      llm_model: intentRouter?.llm?.model || '',
      temperature: intentRouter?.llm?.temperature ?? 0,
      max_tokens: intentRouter?.llm?.max_tokens ?? 1024,
      prompt_template: intentRouter?.prompt_template || '',
    }),
    [intentRouter, validFallbackSkillId],
  );
  const [flowDraft, setFlowDraft] = useState(() =>
    normalizeFlowSchema(intentRouter?.flow),
  );

  const getCandidateSkillsFromFlow = useCallback(() => {
    const examplesBySkillId = new Map<string, string[]>();

    (flowDraft.nodes || []).forEach((node) => {
      if (node.type !== 'condition') {
        return;
      }

      const nodeData = node.data as {
        target_skill_id?: string;
        examples_text?: string;
      };
      const targetSkillId = nodeData.target_skill_id;
      if (!targetSkillId) {
        return;
      }

      const examples = (nodeData.examples_text || '')
        .split('\n')
        .map((item) => item.trim())
        .filter(Boolean);

      if (examples.length > 0) {
        examplesBySkillId.set(targetSkillId, examples);
      }
    });

    return skillOptions.map((skill) => {
      const existingCandidate = intentRouter?.candidate_skills?.find(
        (candidate) => candidate.skill_id === skill.id,
      );

      return {
        skill_id: skill.id,
        label: skill.name,
        description: skill.description,
        enabled: existingCandidate?.enabled ?? skill.enabled ?? true,
        examples:
          examplesBySkillId.get(skill.id) || existingCandidate?.examples || [],
      };
    });
  }, [flowDraft.nodes, intentRouter?.candidate_skills, skillOptions]);

  const [rules, setRules] = useState<IntentRouterRule[]>(
    () => intentRouter?.rules || [],
  );

  const [intentModels, setIntentModels] = useState<LlmProviderModel[]>([]);
  const [selectedProvider, setSelectedProvider] = useState('');

  const uniqueProviders = useMemo(
    () => [...new Set(intentModels.map((m) => m.provider_name))],
    [intentModels],
  );

  const availableModels = useMemo(
    () => intentModels.filter((m) => m.provider_name === selectedProvider),
    [intentModels, selectedProvider],
  );

  const fetchIntentModels = useCallback(async () => {
    try {
      const res = await apiClient.defaultApi.llmConfigurationGet();
      const models = res.data?.models || [];
      setIntentModels(models.filter((m) => m.api === 'intent'));
    } catch (error) {
      console.error(page_bot('failed_to_fetch_llm_config'), error);
    }
  }, []);

  useEffect(() => {
    fetchIntentModels();
  }, [fetchIntentModels]);

  useEffect(() => {
    if (intentRouter?.llm?.provider) {
      setSelectedProvider(intentRouter.llm.provider);
    }
  }, [intentRouter?.llm?.provider]);

  const form = useForm<
    z.input<typeof intentRouterSchema>,
    undefined,
    z.output<typeof intentRouterSchema>
  >({
    resolver: zodResolver(intentRouterSchema),
    defaultValues,
  });

  useEffect(() => {
    form.reset(defaultValues);
  }, [defaultValues, form]);

  useEffect(() => {
    setFlowDraft(normalizeFlowSchema(intentRouter?.flow));
  }, [intentRouter?.flow]);

  const handleSave = form.handleSubmit(async (values) => {
    const nextCandidateSkills = getCandidateSkillsFromFlow();
    const nextOrchestration = {
      ...orchestration,
      intent_router: {
        id: intentRouter?.id || 'main_intent_router',
        name: values.name,
        description: values.description,
        enabled: values.enabled,
        mode: values.mode,
        fallback_skill_id: values.fallback_skill_id || validFallbackSkillId,
        confidence_threshold: values.confidence_threshold,
        llm: {
          provider: values.llm_provider,
          model: values.llm_model,
          temperature: values.temperature,
          max_tokens: values.max_tokens,
        },
        prompt_template: values.prompt_template,
        candidate_skills: nextCandidateSkills,
        rules,
        flow: flowDraft,
        meta: {
          ...(intentRouter?.meta || {}),
          updated_at: new Date().toISOString(),
        },
      },
    };

    await updateBotOrchestration({
      bot,
      orchestration: nextOrchestration,
    });

    await loadBot();
    toast.success(common_tips('update_success'));
    router.refresh();
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>{page_bot('intent_router_title')}</CardTitle>
        <CardDescription>
          {page_bot('intent_router_description')}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Form {...form}>
          <form onSubmit={handleSave} className="flex flex-col gap-6">
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

            <FormField
              control={form.control}
              name="description"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{page_bot('description')}</FormLabel>
                  <FormControl>
                    <Input {...field} value={field.value || ''} />
                  </FormControl>
                </FormItem>
              )}
            />

            <details className="group rounded-md border [&>summary]:flex [&>summary]:cursor-pointer [&>summary]:list-none [&>summary]:items-center [&>summary]:gap-2 [&>summary]:p-3 [&>summary::-webkit-details-marker]:hidden [&[open]>summary]:border-b">
              <summary className="text-sm font-medium select-none">
                {page_bot('model_configuration')}
                <span className="text-muted-foreground transition-transform group-open:rotate-90">
                  ▶
                </span>
              </summary>
              <div className="space-y-3 p-4">
                <FormField
                  control={form.control}
                  name="confidence_threshold"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{page_bot('confidence_threshold')}</FormLabel>
                      <FormControl>
                        <Input
                          type="number"
                          step="0.1"
                          {...field}
                          value={
                            field.value === undefined || field.value === null
                              ? ''
                              : String(field.value)
                          }
                        />
                      </FormControl>
                    </FormItem>
                  )}
                />

                <div className="grid gap-4 md:grid-cols-2">
                  <FormField
                    control={form.control}
                    name="llm_provider"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>
                          {page_bot('intent_model_provider')}
                        </FormLabel>
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
                              <SelectValue
                                placeholder={page_bot('select_provider')}
                              />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            {uniqueProviders.map((p) => (
                              <SelectItem key={p} value={p}>
                                {p}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="llm_model"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>{page_bot('intent_model')}</FormLabel>
                        <Select
                          onValueChange={field.onChange}
                          value={field.value || ''}
                          disabled={availableModels.length === 0}
                        >
                          <FormControl>
                            <SelectTrigger>
                              <SelectValue
                                placeholder={page_bot('select_model')}
                              />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            {availableModels.map((m) => (
                              <SelectItem key={m.model} value={m.model}>
                                {m.model}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </FormItem>
                    )}
                  />
                </div>
              </div>
            </details>

            <details className="group rounded-md border [&>summary]:flex [&>summary]:cursor-pointer [&>summary]:list-none [&>summary]:items-center [&>summary]:gap-2 [&>summary]:p-3 [&>summary::-webkit-details-marker]:hidden [&[open]>summary]:border-b">
              <summary className="text-sm font-medium select-none">
                {page_bot('intent_prompt')}
                <span className="text-muted-foreground transition-transform group-open:rotate-90">
                  ▶
                </span>
              </summary>
              <div className="p-4">
                <FormField
                  control={form.control}
                  name="prompt_template"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{page_bot('query_prompt_template')}</FormLabel>
                      <FormControl>
                        <Textarea
                          {...field}
                          value={field.value || ''}
                          className="h-40 font-mono text-sm"
                        />
                      </FormControl>
                    </FormItem>
                  )}
                />
              </div>
            </details>

            <FormField
              control={form.control}
              name="enabled"
              render={({ field }) => (
                <FormItem className="flex flex-row items-center justify-between rounded-lg border p-4">
                  <FormLabel>{page_bot('orchestration_configured')}</FormLabel>
                  <FormControl>
                    <Switch
                      checked={field.value}
                      onCheckedChange={field.onChange}
                    />
                  </FormControl>
                </FormItem>
              )}
            />

            <div className="grid gap-4 md:grid-cols-2">
              <FormField
                control={form.control}
                name="mode"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{page_bot('mode')}</FormLabel>
                    <Select onValueChange={field.onChange} value={field.value}>
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        <SelectItem value="llm">
                          {page_bot('llm_only')}
                        </SelectItem>
                        <SelectItem value="rules+llm">
                          {page_bot('rules_and_llm')}
                        </SelectItem>
                      </SelectContent>
                    </Select>
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="fallback_skill_id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{page_bot('skills_title')}</FormLabel>
                    <Select
                      onValueChange={field.onChange}
                      value={field.value}
                      disabled={skillOptions.length === 0}
                    >
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue
                            placeholder={page_bot(
                              'orchestration_not_configured',
                            )}
                          />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {skillOptions.map((skill) => (
                          <SelectItem key={skill.id} value={skill.id}>
                            {skill.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </FormItem>
                )}
              />
            </div>

            <details
              className="group rounded-md border [&>summary]:flex [&>summary]:cursor-pointer [&>summary]:list-none [&>summary]:items-center [&>summary]:gap-2 [&>summary]:p-3 [&>summary::-webkit-details-marker]:hidden [&[open]>summary]:border-b"
              open={form.watch('mode') === 'rules+llm'}
            >
              <summary className="text-sm font-medium select-none">
                {page_bot('hard_rules')}
                <span className="text-muted-foreground transition-transform group-open:rotate-90">
                  ▶
                </span>
              </summary>
              <div className="space-y-3 p-4">
                <p className="text-muted-foreground text-xs">
                  {page_bot('hard_rules_description')}
                </p>
                {rules.map((rule, idx) => (
                  <div
                    key={idx}
                    className="flex items-center gap-2 rounded-md border p-3"
                  >
                    <Select
                      value={rule.rule_type}
                      onValueChange={(val) => {
                        const next = [...rules];
                        next[idx] = {
                          ...next[idx],
                          rule_type: val as 'keyword' | 'regex',
                        };
                        setRules(next);
                      }}
                    >
                      <SelectTrigger className="w-28">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="keyword">
                          {page_bot('rule_type_keyword')}
                        </SelectItem>
                        <SelectItem value="regex">
                          {page_bot('rule_type_regex')}
                        </SelectItem>
                      </SelectContent>
                    </Select>
                    <Input
                      value={rule.value}
                      onChange={(e) => {
                        const next = [...rules];
                        next[idx] = { ...next[idx], value: e.target.value };
                        setRules(next);
                      }}
                      placeholder={getRulePlaceholder(rule.rule_type)}
                      className="flex-1"
                    />
                    <Select
                      value={rule.target_skill_id}
                      onValueChange={(val) => {
                        const next = [...rules];
                        next[idx] = { ...next[idx], target_skill_id: val };
                        setRules(next);
                      }}
                    >
                      <SelectTrigger className="w-36">
                        <SelectValue placeholder={page_bot('target_skill')} />
                      </SelectTrigger>
                      <SelectContent>
                        {skillOptions.map((s) => (
                          <SelectItem key={s.id} value={s.id}>
                            {s.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="size-8"
                      onClick={() =>
                        setRules(rules.filter((_, i) => i !== idx))
                      }
                    >
                      ×
                    </Button>
                  </div>
                ))}
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() =>
                    setRules([
                      ...rules,
                      {
                        rule_type: 'keyword',
                        value: '',
                        target_skill_id: validFallbackSkillId || '',
                        enabled: true,
                      },
                    ])
                  }
                >
                  {page_bot('add_rule')}
                </Button>
              </div>
            </details>

            <div className="grid gap-4 md:grid-cols-2">
              <FormField
                control={form.control}
                name="temperature"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{page_bot('temperature')}</FormLabel>
                    <FormControl>
                      <Input
                        type="number"
                        step="0.1"
                        {...field}
                        value={
                          field.value === undefined || field.value === null
                            ? ''
                            : String(field.value)
                        }
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
                    <FormLabel>{page_bot('max_tokens')}</FormLabel>
                    <FormControl>
                      <Input
                        type="number"
                        {...field}
                        value={
                          field.value === undefined || field.value === null
                            ? ''
                            : String(field.value)
                        }
                      />
                    </FormControl>
                  </FormItem>
                )}
              />
            </div>

            <FlowCanvasEditor
              title={page_bot('intent_router_flow_canvas_title')}
              description={page_bot('intent_router_flow_canvas_description')}
              value={flowDraft}
              onChange={setFlowDraft}
              skillOptions={skillOptions.map((skill) => ({
                id: skill.id,
                label: skill.name,
              }))}
              mode="intent-router"
            />

            <details className="group rounded-md border [&>summary]:flex [&>summary]:cursor-pointer [&>summary]:list-none [&>summary]:items-center [&>summary]:gap-2 [&>summary]:p-3 [&>summary::-webkit-details-marker]:hidden [&[open]>summary]:border-b">
              <summary className="font-medium select-none">
                {page_bot('intent_router_flow_title')}
                <span className="transition-transform group-open:rotate-90">
                  ▶
                </span>
              </summary>
              <div className="p-4">
                <FlowJsonEditor
                  title={page_bot('intent_router_flow_title')}
                  description={page_bot('intent_router_flow_description')}
                  value={flowDraft}
                  onChange={setFlowDraft}
                />
              </div>
            </details>

            <div className="flex gap-3">
              <Button variant="outline" asChild>
                <Link href={`/workspace/bots/${bot.id}/settings`}>
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
