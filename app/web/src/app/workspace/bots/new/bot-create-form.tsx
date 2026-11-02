'use client';

import { Bot, ModelSpec } from '@/api';
import { BotConfigProvider } from '@/components/providers/bot-config-provider';
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
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
} from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Switch } from '@/components/ui/switch';
import { apiClient } from '@/lib/api/client';
import { zodResolver } from '@hookform/resolvers/zod';
import _ from 'lodash';
import { useTranslations } from 'next-intl';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useForm, useWatch } from 'react-hook-form';
import { BotOrchestrationCard } from '../[botId]/bot-orchestration-card';
import type { BotConfigWithOrchestration } from '../[botId]/orchestration-types';
import {
  DEFAULT_AGENT_QUERY_PROMPT,
  DEFAULT_AGENT_SYSTEM_PROMPT,
  DEFAULT_AGENT_WELCOME_SUBTITLE,
  DEFAULT_AGENT_WELCOME_TITLE,
} from '../agent-defaults';

import { toast } from 'sonner';
import * as z from 'zod';

const botCreateModelSchema = z
  .object({
    custom_llm_provider: z.string(),
    model: z.string(),
    model_service_provider: z.string(),
  })
  .optional();

const botCreateSchema = z.object({
  title: z.string().min(1),
  description: z.string(),
  is_default: z.boolean().optional(),
  type: z.enum(['knowledge', 'common', 'agent']),
  config: z.object({
    agent: z.object({
      completion: botCreateModelSchema,
      welcome_title: z.string(),
      welcome_subtitle: z.string(),
      system_prompt_template: z.string(),
      query_prompt_template: z.string(),
    }),
  }),
});

type FormValueType = z.infer<typeof botCreateSchema>;

export type ProviderModel = {
  label?: string;
  name?: string;
  models?: ModelSpec[];
};

export const BotCreateForm = ({ sourceBot }: { sourceBot?: Bot | null }) => {
  const router = useRouter();
  const [completionModels, setCompletionModels] = useState<ProviderModel[]>();
  const [confirmDialogOpen, setConfirmDialogOpen] = useState(false);
  const [pendingValues, setPendingValues] = useState<FormValueType | null>(
    null,
  );
  const [defaultBotName, setDefaultBotName] = useState('');

  const page_bot = useTranslations('page_bot');
  const common_tips = useTranslations('common.tips');
  const common_action = useTranslations('common.action');
  const sourceBotConfig = (sourceBot?.config ||
    {}) as BotConfigWithOrchestration;
  const sourceAgentConfig = sourceBotConfig.agent;

  const defaultValues = useMemo<FormValueType>(
    () => ({
      title: '',
      description: '',
      is_default: false,
      type: sourceBot?.type || 'agent',
      config: {
        agent: {
          completion: sourceAgentConfig?.completion
            ? {
                custom_llm_provider:
                  sourceAgentConfig.completion.custom_llm_provider || '',
                model: sourceAgentConfig.completion.model || '',
                model_service_provider:
                  sourceAgentConfig.completion.model_service_provider || '',
              }
            : {
                custom_llm_provider: '',
                model: '',
                model_service_provider: '',
              },
          welcome_title:
            sourceAgentConfig?.welcome_title || DEFAULT_AGENT_WELCOME_TITLE,
          welcome_subtitle:
            sourceAgentConfig?.welcome_subtitle ||
            DEFAULT_AGENT_WELCOME_SUBTITLE,
          system_prompt_template:
            sourceAgentConfig?.system_prompt_template ||
            DEFAULT_AGENT_SYSTEM_PROMPT,
          query_prompt_template:
            sourceAgentConfig?.query_prompt_template ||
            DEFAULT_AGENT_QUERY_PROMPT,
        },
      },
    }),
    [sourceAgentConfig, sourceBot?.type],
  );

  const form = useForm<FormValueType>({
    resolver: zodResolver(botCreateSchema),
    defaultValues,
  });

  const loadModels = useCallback(async () => {
    const res = await apiClient.defaultApi.availableModelsPost({
      tagFilterRequest: {
        tag_filters: [{ operation: 'AND', tags: ['enable_for_agent'] }],
      },
    });
    const completion = res.data.items?.map((m) => {
      return {
        label: m.label,
        name: m.name,
        models: m.completion,
      };
    });
    setCompletionModels(completion || []);
  }, []);

  const tempBot = useMemo<Bot>(
    () =>
      ({
        config: {
          flow: sourceBotConfig.flow,
          orchestration: sourceBotConfig.orchestration || {},
        },
      }) as Bot,
    [sourceBotConfig.flow, sourceBotConfig.orchestration],
  );

  const handleSubmit = useCallback(
    async (values: FormValueType) => {
      if (values.is_default) {
        const res = await apiClient.defaultApi.botsGet({
          page: 1,
          pageSize: 100,
        });
        const bots = res.data.items || [];
        const defaultBot = bots.find((b) => b.is_default);
        if (defaultBot) {
          setDefaultBotName(defaultBot.title || '');
          setPendingValues(values);
          setConfirmDialogOpen(true);
          return;
        }
      }

      await executeCreate(values, false);
    },
    [common_tips, router],
  );

  const executeCreate = useCallback(
    async (values: FormValueType, clearOldDefault: boolean) => {
      const botCreate = {
        title: values.title,
        description: values.description,
        is_default: values.is_default,
        type: values.type,
        config: {
          agent: {
            completion: values.config.agent.completion,
            welcome_title: values.config.agent.welcome_title,
            welcome_subtitle: values.config.agent.welcome_subtitle,
            system_prompt_template: values.config.agent.system_prompt_template,
            query_prompt_template: values.config.agent.query_prompt_template,
          },
          flow: sourceBotConfig.flow,
          orchestration: sourceBotConfig.orchestration,
        },
      };

      const res = await apiClient.defaultApi.botsPost({
        botCreate,
      });

      if (res.data.id && clearOldDefault) {
        const botsRes = await apiClient.defaultApi.botsGet({
          page: 1,
          pageSize: 100,
        });
        const bots = botsRes.data.items || [];
        const defaultBot = bots.find(
          (b) => b.is_default && b.id !== res.data.id,
        );
        if (defaultBot) {
          await apiClient.defaultApi.botsBotIdPut({
            botId: defaultBot.id || '',
            botUpdate: {
              is_default: false,
            },
          });
        }
      }

      if (res.data.id) {
        toast.success(common_tips('create_success'));
        router.push(`/workspace/bots/${res.data.id}/edit`);
      }
    },
    [common_tips, router, sourceBotConfig.flow, sourceBotConfig.orchestration],
  );

  const handleConfirm = useCallback(async () => {
    setConfirmDialogOpen(false);
    if (pendingValues) {
      await executeCreate(pendingValues, true);
    }
  }, [pendingValues, executeCreate]);

  const completionModelName = useWatch({
    control: form.control,
    name: 'config.agent.completion.model',
  });

  useEffect(() => {
    if (_.isEmpty(completionModels)) return;

    let defaultModel: ModelSpec | undefined;
    let currentModel: ModelSpec | undefined;
    let defaultProvider: ProviderModel | undefined;
    let currentProvider: ProviderModel | undefined;

    completionModels?.forEach((provider) => {
      provider.models?.forEach((m) => {
        if (m.tags?.some((t) => t === 'default_for_agent')) {
          defaultModel = m;
          defaultProvider = provider;
        }
        if (m.model === completionModelName) {
          currentModel = m;
          currentProvider = provider;
        }
      });
    });

    if (currentModel) {
      form.setValue(
        'config.agent.completion.custom_llm_provider',
        currentModel.custom_llm_provider || '',
      );
      form.setValue(
        'config.agent.completion.model_service_provider',
        currentProvider?.name || defaultProvider?.name || '',
      );
      form.setValue(
        'config.agent.completion.model',
        currentModel.model || defaultModel?.model || '',
      );
    }
  }, [completionModelName, completionModels, form]);

  useEffect(() => {
    loadModels();
  }, [loadModels]);

  useEffect(() => {
    form.reset(defaultValues);
  }, [defaultValues, form]);

  return (
    <Form {...form}>
      <form
        onSubmit={form.handleSubmit(handleSubmit)}
        className="flex flex-col gap-4"
      >
        <Card>
          <CardHeader>
            <CardTitle>{page_bot('general')}</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-6">
            <FormField
              control={form.control}
              name="title"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{page_bot('title')}</FormLabel>
                  <FormControl>
                    <Input
                      className="md:w-6/12"
                      placeholder={page_bot('title_placeholder')}
                      {...field}
                      value={field.value || ''}
                    />
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
                    <Textarea
                      className="h-24"
                      placeholder={page_bot('description_placeholder')}
                      {...field}
                      value={field.value || ''}
                    />
                  </FormControl>
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="is_default"
              render={({ field }) => (
                <FormItem className="flex flex-row items-center justify-between rounded-lg border p-4">
                  <div className="space-y-0.5">
                    <FormLabel className="text-base">
                      {page_bot('is_default')}
                    </FormLabel>
                    <FormDescription>
                      {page_bot('is_default_description')}
                    </FormDescription>
                  </div>
                  <FormControl>
                    <Switch
                      checked={field.value || false}
                      onCheckedChange={field.onChange}
                    />
                  </FormControl>
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="config.agent.welcome_title"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{page_bot('welcome_title')}</FormLabel>
                  <FormControl>
                    <Input
                      className="md:w-6/12"
                      placeholder={page_bot('welcome_title_placeholder')}
                      {...field}
                      value={field.value || ''}
                    />
                  </FormControl>
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="config.agent.welcome_subtitle"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{page_bot('welcome_subtitle')}</FormLabel>
                  <FormControl>
                    <Textarea
                      className="h-20"
                      placeholder={page_bot('welcome_subtitle_placeholder')}
                      {...field}
                      value={field.value || ''}
                    />
                  </FormControl>
                  <FormDescription>
                    {page_bot('welcome_description')}
                  </FormDescription>
                </FormItem>
              )}
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{page_bot('model_config')}</CardTitle>
            <CardDescription>{page_bot('model_description')}</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-6 pt-6">
            <FormField
              control={form.control}
              name="config.agent.completion.model"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{page_bot('model')}</FormLabel>
                  <FormControl>
                    <Select
                      {...field}
                      onValueChange={field.onChange}
                      value={field.value || ''}
                    >
                      <SelectTrigger className="w-full cursor-pointer md:w-6/12">
                        <SelectValue
                          placeholder={page_bot('model_placeholder')}
                        />
                      </SelectTrigger>
                      <SelectContent>
                        {completionModels
                          ?.filter((item) => _.size(item.models))
                          .map((item) => {
                            return (
                              <SelectGroup key={item.name}>
                                <SelectLabel>{item.label}</SelectLabel>
                                {item.models?.map((model) => {
                                  return (
                                    <SelectItem
                                      key={model.model}
                                      value={model.model || ''}
                                    >
                                      {model.model}
                                    </SelectItem>
                                  );
                                })}
                              </SelectGroup>
                            );
                          })}
                      </SelectContent>
                    </Select>
                  </FormControl>
                </FormItem>
              )}
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{page_bot('system_prompt_template')}</CardTitle>
            <CardDescription>
              {page_bot('system_prompt_template_description')}
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-6 pt-6">
            <FormField
              control={form.control}
              name="config.agent.system_prompt_template"
              render={({ field }) => (
                <FormItem>
                  <FormControl>
                    <Textarea
                      className="h-48 font-mono text-sm"
                      placeholder={page_bot(
                        'system_prompt_template_placeholder',
                      )}
                      {...field}
                      value={field.value || ''}
                    />
                  </FormControl>
                </FormItem>
              )}
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{page_bot('query_prompt_template')}</CardTitle>
            <CardDescription>
              {page_bot('query_prompt_template_description')}
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-6 pt-6">
            <FormField
              control={form.control}
              name="config.agent.query_prompt_template"
              render={({ field }) => (
                <FormItem>
                  <FormControl>
                    <Textarea
                      className="h-32 font-mono text-sm"
                      placeholder={page_bot(
                        'query_prompt_template_placeholder',
                      )}
                      {...field}
                      value={field.value || ''}
                    />
                  </FormControl>
                </FormItem>
              )}
            />
          </CardContent>
        </Card>

        <BotConfigProvider bot={tempBot}>
          <BotOrchestrationCard />
        </BotConfigProvider>

        <div className="flex justify-end gap-4">
          <Button variant="outline" asChild>
            <Link href="/workspace/bots">{common_action('cancel')}</Link>
          </Button>
          <Button type="submit" className="cursor-pointer px-6">
            {page_bot('save_bot')}
          </Button>
        </div>

        <AlertDialog
          open={confirmDialogOpen}
          onOpenChange={setConfirmDialogOpen}
        >
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>
                {page_bot('default_conflict_title')}
              </AlertDialogTitle>
              <AlertDialogDescription>
                {page_bot('default_conflict_message', { name: defaultBotName })}
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>{page_bot('cancel')}</AlertDialogCancel>
              <AlertDialogAction onClick={handleConfirm}>
                {page_bot('confirm')}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </form>
    </Form>
  );
};
