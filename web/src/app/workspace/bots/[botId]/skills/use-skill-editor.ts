'use client';

import { LlmProviderModel } from '@/api';
import { useBotConfigContext } from '@/components/providers/bot-config-provider';
import { apiClient } from '@/lib/api/client';
import { zodResolver } from '@hookform/resolvers/zod';
import { useMessages, useTranslations } from 'next-intl';
import { useRouter } from 'next/navigation';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useForm } from 'react-hook-form';
import { toast } from 'sonner';
import {
  normalizeOrchestration,
  updateBotOrchestration,
} from '../bot-config-updater';
import { normalizeFlowSchema } from '../flow-utils';
import type { MCPToolInfo, ReactFlowSchema } from '../orchestration-types';
import {
  buildSkillOrchestration,
  skillSchema,
  type SkillEditorFormInput,
  type SkillEditorFormValues,
} from './skill-config';

export const useSkillEditor = (skillId?: string) => {
  const { bot, loadBot } = useBotConfigContext();
  const page_bot = useTranslations('page_bot');
  const messages = useMessages() as Record<string, any>;
  const common_tips = useTranslations('common.tips');
  const router = useRouter();

  const getLocalizedToolDescription = useCallback(
    (toolName: string, fallback?: string) => {
      const descriptionKey = `tool_desc_${toolName}`;
      const pageBotMessages = messages?.page_bot as
        | Record<string, string>
        | undefined;

      if (pageBotMessages && descriptionKey in pageBotMessages) {
        return page_bot(descriptionKey as any);
      }

      return fallback || '';
    },
    [messages, page_bot],
  );

  const orchestration = normalizeOrchestration(bot);
  const existingSkill = useMemo(
    () => orchestration.skills?.find((skill) => skill.id === skillId),
    [orchestration.skills, skillId],
  );

  const [collections, setCollections] = useState<
    { id?: string; title?: string }[]
  >([]);
  const [availableTools, setAvailableTools] = useState<MCPToolInfo[]>([]);

  const loadCollections = useCallback(async () => {
    const res = await apiClient.defaultApi.collectionsGet();
    setCollections(res.data.items || []);
  }, []);

  const loadTools = useCallback(async () => {
    try {
      const res = await fetch('/api/v1/mcp_tools');
      if (res.ok) {
        const data = await res.json();
        setAvailableTools(Array.isArray(data) ? data : []);
      }
    } catch (e) {
      console.error('Failed to load MCP tools', e);
    }
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
      tools: existingSkill?.tools?.filter((t) => t.tool_id) || [],
    }),
    [existingSkill],
  );
  const [flowDraft, setFlowDraft] = useState(() =>
    normalizeFlowSchema(existingSkill?.flow),
  );

  useEffect(() => {
    loadCollections();
    loadTools();
  }, [loadCollections, loadTools]);

  const [completionModels, setCompletionModels] = useState<LlmProviderModel[]>(
    [],
  );
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
      const models = items
        .flatMap((item) =>
          (item.completion || []).map((model): LlmProviderModel | null => {
            if (!item.name || !model.model || !model.custom_llm_provider) {
              return null;
            }

            return {
              ...model,
              provider_name: item.name,
              model: model.model,
              custom_llm_provider: model.custom_llm_provider,
              api: 'completion',
            };
          }),
        )
        .filter((model): model is LlmProviderModel => model !== null);
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

  const form = useForm<SkillEditorFormInput, undefined, SkillEditorFormValues>({
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
        toast.error(page_bot('only_one_fallback_skill_error'));
        return;
      }
    }

    await updateBotOrchestration({
      bot,
      orchestration: buildSkillOrchestration({
        orchestration,
        existingSkill,
        skillId,
        values,
        flow: flowDraft,
        deduplicateSkills: true,
        updatedAt: new Date().toISOString(),
      }),
    });

    await loadBot();
    toast.success(common_tips('update_success'));
    router.push(`/workspace/bots/${bot.id}/skills`);
    router.refresh();
  });

  // Quick save intentionally bypasses Zod, the fallback guard and deduplication.
  const handleQuickSave = async (nextFlow: ReactFlowSchema) => {
    const values = form.getValues() as SkillEditorFormValues;
    await updateBotOrchestration({
      bot,
      orchestration: buildSkillOrchestration({
        orchestration,
        existingSkill,
        skillId,
        values,
        flow: nextFlow,
        deduplicateSkills: false,
        updatedAt: new Date().toISOString(),
      }),
    });
    await loadBot();
    return true;
  };

  return {
    bot,
    existingSkill,
    form,
    flowDraft,
    setFlowDraft,
    collections,
    uniqueProviders,
    availableModels,
    setSelectedProvider,
    handleSave,
    handleQuickSave,
    skillOptions: (orchestration.skills || []).map((skill) => ({
      id: skill.id,
      label: skill.name,
    })),
    skillTools: availableTools.map((tool) => ({
      id: tool.name,
      name: tool.name,
      description: getLocalizedToolDescription(tool.name, tool.description),
    })),
  };
};
