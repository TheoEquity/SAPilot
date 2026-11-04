import { apiClient } from '@/lib/api/client';
import type { Bot } from '@/api/models/bot';
import type {
  BotConfigWithOrchestration,
  OrchestrationConfig,
} from './orchestration-types';

const normalizeBotConfig = (bot: Bot): BotConfigWithOrchestration => {
  return {
    ...(bot.config || {}),
    orchestration: {
      ...(bot.config as BotConfigWithOrchestration | undefined)?.orchestration,
      skills:
        (bot.config as BotConfigWithOrchestration | undefined)?.orchestration
          ?.skills || [],
    },
  };
};

export const updateBotOrchestration = async ({
  bot,
  orchestration,
}: {
  bot: Bot;
  orchestration: OrchestrationConfig;
}) => {
  if (!bot.id) {
    throw new Error('Bot id is required');
  }

  const currentConfig = normalizeBotConfig(bot);
  const nextConfig: BotConfigWithOrchestration = {
    agent: currentConfig.agent,
    flow: currentConfig.flow,
    orchestration,
  };

  await apiClient.defaultApi.botsBotIdPut({
    botId: bot.id,
    botUpdate: {
      title: bot.title,
      description: bot.description,
      is_default: bot.is_default,
      config: nextConfig,
    },
  });
};

export const normalizeOrchestration = (
  bot: Bot,
): OrchestrationConfig => {
  return normalizeBotConfig(bot).orchestration || { skills: [] };
};
