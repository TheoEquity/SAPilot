import type { Bot } from '@/api/generated/models';
import { apiClient } from '@/lib/api/client';
import type {
  BotConfigWithOrchestration,
  OrchestrationConfig,
} from './orchestration-types';
import { toBotConfigInput } from './orchestration-types';

const normalizeBotConfig = (bot: Bot): BotConfigWithOrchestration => {
  return {
    ...(bot.config || {}),
    orchestration: {
      ...bot.config?.orchestration,
      skills: bot.config?.orchestration?.skills || [],
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

  await apiClient.bots.updateBot(encodeURIComponent(String(bot.id)), {
    title: bot.title,
    description: bot.description,
    is_default: bot.is_default,
    config: toBotConfigInput(nextConfig),
  });
};

export const normalizeOrchestration = (bot: Bot): OrchestrationConfig => {
  return normalizeBotConfig(bot).orchestration || { skills: [] };
};
