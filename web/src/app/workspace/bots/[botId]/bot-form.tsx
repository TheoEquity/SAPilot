'use client';

import { ModelSpec } from '@/api';
import { useBotConfigContext } from '@/components/providers/bot-config-provider';
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
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command';
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
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { Textarea } from '@/components/ui/textarea';
import { apiClient } from '@/lib/api/client';
import { cn } from '@/lib/utils';
import { zodResolver } from '@hookform/resolvers/zod';
import _ from 'lodash';
import { Check, ChevronsUpDown, X } from 'lucide-react';
import { useTranslations } from 'next-intl';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useCallback, useEffect, useState } from 'react';
import { useForm, useWatch } from 'react-hook-form';
import { toast } from 'sonner';
import * as z from 'zod';

const botConfigAgentModelSchema = z
  .object({
    custom_llm_provider: z.string(),
    model: z.string(),
    model_service_provider: z.string(),
  })
  .optional();

const botConfigSchema = z.object({
  title: z.string().min(1),
  description: z.string(),
  is_default: z.boolean().optional(),
  config: z.object({
    agent: z.object({
      completion: botConfigAgentModelSchema,
      welcome_title: z.string(),
      welcome_subtitle: z.string(),
      system_prompt_template: z.string(),
      query_prompt_template: z.string(),
      collections: z.array(z.object({ id: z.string() })).optional(),
    }),
  }),
});

type FormValueType = z.infer<typeof botConfigSchema>;

export type ProviderModel = {
  label?: string;
  name?: string;
  models?: ModelSpec[];
};

const DEFAULT_SYSTEM_PROMPT = `You are a helpful AI assistant. Answer user questions based on the provided context and your knowledge. If you don't know the answer, say so clearly.`;

const DEFAULT_QUERY_PROMPT = `Answer the following question based on the provided context:

{query}`;

const DEFAULT_WELCOME_TITLE = 'Hi, 我是 SAPilot.';

const DEFAULT_WELCOME_SUBTITLE =
  'SAPilot 是面向 SAP 运维场景的智能助手，可结合企业知识库与运维经验，帮助顾问快速定位问题、分析原因并提供处理建议。';

export const BotForm = () => {
  const router = useRouter();
  const { bot, collections, loadBot } = useBotConfigContext();
  const [completionModels, setCompletionModels] = useState<ProviderModel[]>();
  const [confirmDialogOpen, setConfirmDialogOpen] = useState(false);
  const [pendingValues, setPendingValues] = useState<FormValueType | null>(
    null,
  );
  const [defaultBotName, setDefaultBotName] = useState('');

  const page_bot = useTranslations('page_bot');
  const common_tips = useTranslations('common.tips');
  const common_action = useTranslations('common.action');

  const agentConfig = bot.config?.agent;
  const selectedCollectionIds =
    agentConfig?.collections?.map((c) => c.id).filter(Boolean) || [];
  const completion = agentConfig?.completion;

  const defaultValues: FormValueType = {
    title: bot.title || '',
    description: bot.description || '',
    is_default: bot.is_default || false,
    config: {
      agent: {
        completion: completion
          ? {
              custom_llm_provider: completion.custom_llm_provider || '',
              model: completion.model || '',
              model_service_provider: completion.model_service_provider || '',
            }
          : {
              custom_llm_provider: '',
              model: '',
              model_service_provider: '',
            },
        welcome_title: agentConfig?.welcome_title || DEFAULT_WELCOME_TITLE,
        welcome_subtitle:
          agentConfig?.welcome_subtitle || DEFAULT_WELCOME_SUBTITLE,
        system_prompt_template:
          agentConfig?.system_prompt_template || DEFAULT_SYSTEM_PROMPT,
        query_prompt_template:
          agentConfig?.query_prompt_template || DEFAULT_QUERY_PROMPT,
        collections:
          agentConfig?.collections
            ?.map((collection) => collection.id)
            .filter((id): id is string => Boolean(id))
            .map((id) => ({ id })) || [],
      },
    },
  };

  const form = useForm<FormValueType>({
    resolver: zodResolver(botConfigSchema),
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

  const executeSave = useCallback(
    async (values: FormValueType, clearOldDefault: boolean) => {
      if (!bot?.id) return;

      const selectedCollections = collections.filter((c) =>
        values.config.agent.collections?.some((sc) => sc.id === c.id),
      );

      const botUpdate = {
        title: values.title,
        description: values.description,
        is_default: values.is_default,
        config: {
          agent: {
            completion: values.config.agent.completion,
            welcome_title: values.config.agent.welcome_title,
            welcome_subtitle: values.config.agent.welcome_subtitle,
            system_prompt_template: values.config.agent.system_prompt_template,
            query_prompt_template: values.config.agent.query_prompt_template,
            collections: selectedCollections,
          },
        },
      };

      if (clearOldDefault) {
        const botsRes = await apiClient.defaultApi.botsGet({
          page: 1,
          pageSize: 100,
        });
        const bots = botsRes.data.items || [];
        const defaultBot = bots.find((b) => b.is_default && b.id !== bot.id);
        if (defaultBot?.id) {
          await apiClient.defaultApi.botsBotIdPut({
            botId: defaultBot.id,
            botUpdate: {
              is_default: false,
            },
          });
        }
      }

      await apiClient.defaultApi.botsBotIdPut({
        botId: bot.id,
        botUpdate,
      });

      toast.success(common_tips('update_success'));
      loadBot();
    },
    [bot?.id, bot.config, collections, common_tips, loadBot],
  );

  const handleSubmit = useCallback(
    async (values: FormValueType) => {
      if (values.is_default && !bot.is_default) {
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

      await executeSave(values, false);
    },
    [bot.is_default, executeSave],
  );

  const handleConfirm = useCallback(async () => {
    setConfirmDialogOpen(false);
    if (pendingValues) {
      await executeSave(pendingValues, true);
    }
  }, [pendingValues, executeSave]);

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

  const handleRestoreSystemPrompt = () => {
    form.setValue('config.agent.system_prompt_template', DEFAULT_SYSTEM_PROMPT);
  };

  const handleRestoreQueryPrompt = () => {
    form.setValue('config.agent.query_prompt_template', DEFAULT_QUERY_PROMPT);
  };

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
            <CardTitle>{page_bot('collection')}</CardTitle>
            <CardDescription>
              {page_bot('collection_description')}
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-6 pt-6">
            <FormField
              control={form.control}
              name="config.agent.collections"
              render={({ field }) => {
                const selectedIds = field.value?.map((c) => c.id) || [];
                const selectedItems = collections.filter((c) =>
                  c.id ? selectedIds.includes(c.id) : false,
                );

                return (
                  <FormItem>
                    <FormLabel>{page_bot('collection')}</FormLabel>
                    <FormControl>
                      <Popover>
                        <PopoverTrigger asChild>
                          <Button
                            variant="outline"
                            role="combobox"
                            className="w-full justify-between md:w-6/12"
                          >
                            {selectedItems.length > 0
                              ? page_bot('collection_selected', {
                                  count: String(selectedItems.length),
                                })
                              : page_bot('collection_placeholder')}
                            <ChevronsUpDown className="ml-2 size-4 shrink-0 opacity-50" />
                          </Button>
                        </PopoverTrigger>
                        <PopoverContent className="w-full p-0 md:w-6/12">
                          <Command>
                            <CommandInput
                              placeholder={page_bot('collection_search')}
                            />
                            <CommandList>
                              <CommandEmpty>
                                {page_bot('no_collection_found')}
                              </CommandEmpty>
                              <CommandGroup>
                                {collections.map((collection) => {
                                  const isSelected = selectedIds.includes(
                                    collection.id || '',
                                  );
                                  return (
                                    <CommandItem
                                      key={collection.id}
                                      value={collection.id || ''}
                                      onSelect={() => {
                                        const current = field.value || [];
                                        if (isSelected) {
                                          form.setValue(
                                            'config.agent.collections',
                                            current.filter(
                                              (c) => c.id !== collection.id,
                                            ),
                                          );
                                        } else {
                                          if (!collection.id) return;
                                          form.setValue(
                                            'config.agent.collections',
                                            [...current, { id: collection.id }],
                                          );
                                        }
                                      }}
                                    >
                                      <Check
                                        className={cn(
                                          'mr-2 size-4',
                                          isSelected
                                            ? 'opacity-100'
                                            : 'opacity-0',
                                        )}
                                      />
                                      {collection.title}
                                    </CommandItem>
                                  );
                                })}
                              </CommandGroup>
                            </CommandList>
                          </Command>
                        </PopoverContent>
                      </Popover>
                    </FormControl>
                    {selectedItems.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-2">
                        {selectedItems.map((c) => (
                          <Badge
                            key={c.id}
                            variant="secondary"
                            className="gap-1 pr-1"
                          >
                            {c.title}
                            <button
                              type="button"
                              className="hover:bg-accent ml-1 rounded-full"
                              onClick={() => {
                                const current = field.value || [];
                                form.setValue(
                                  'config.agent.collections',
                                  current.filter((item) => item.id !== c.id),
                                );
                              }}
                            >
                              <X className="size-3" />
                            </button>
                          </Badge>
                        ))}
                      </div>
                    )}
                  </FormItem>
                );
              }}
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
                  <div className="flex justify-end">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={handleRestoreSystemPrompt}
                    >
                      {page_bot('restore_to_default')}
                    </Button>
                  </div>
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
                  <div className="flex justify-end">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={handleRestoreQueryPrompt}
                    >
                      {page_bot('restore_to_default')}
                    </Button>
                  </div>
                </FormItem>
              )}
            />
          </CardContent>
        </Card>

        <div className="flex justify-end gap-4">
          <Button variant="outline" asChild>
            <Link href="/workspace/bots">{common_action('cancel')}</Link>
          </Button>
          <Button type="submit" className="cursor-pointer px-6">
            {page_bot('save_settings')}
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
