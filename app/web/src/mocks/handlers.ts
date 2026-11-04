import { HttpResponse } from 'msw';
import { randomUUID } from 'node:crypto';
import {
  getCreateBotMockHandler,
  getDeleteBotMockHandler,
  getGetBotMockHandler,
  getListBotsMockHandler,
  getUpdateBotMockHandler,
} from '../api/generated/bots/bots.msw';
import { getListChatsViewApiV1BotsBotIdChatsGetMockHandler } from '../api/generated/chats/chats.msw';
import { getListCollectionsViewApiV1CollectionsGetMockHandler } from '../api/generated/collections/collections.msw';
import { getConfigViewApiV1ConfigGetMockHandler } from '../api/generated/config/config.msw';
import * as generatedMocks from '../api/generated/index.msw';
import { getGetAvailableModelsViewApiV1AvailableModelsPostMockHandler } from '../api/generated/llm-models/llm-models.msw';
import type { Bot, BotList, ModelConfigList } from '../api/generated/models';
import { getGetUserViewApiV1UserGetMockHandler } from '../api/generated/users/users.msw';

export type MockScenario = 'default' | 'empty' | 'error';

function reject(status: number, detail: string): never {
  throw HttpResponse.json({ detail }, { status });
}

/** One in-memory store shared by browser proxy requests and Next server reads. */
export function createMockHandlers(scenario: MockScenario = 'default') {
  const bots = new Map<string, Bot>();
  if (scenario !== 'empty') {
    bots.set('mock-bot', {
      id: 'mock-bot',
      title: 'Mock SAP Bot',
      description: 'Local development data',
      type: 'agent',
      is_default: true,
      is_protected: true,
      config: { agent: {}, orchestration: { skills: [] } },
      created: '2026-01-01T00:00:00Z',
      updated: '2026-01-01T00:00:00Z',
    });
  }

  const availableModels: ModelConfigList = {
    items: [
      {
        name: 'mock-provider',
        label: 'Mock provider',
        completion: [
          {
            model: 'mock-model',
            model_service_provider: 'mock-provider',
            custom_llm_provider: 'openai',
          },
        ],
      },
    ],
  };
  function requireBot(id: string) {
    return bots.get(id) ?? reject(404, 'Bot not found');
  }
  function checkScenario() {
    if (scenario === 'error') reject(500, 'Mock Bot request failed');
  }

  return [
    getGetUserViewApiV1UserGetMockHandler({
      id: 'mock-user',
      username: 'mock-developer',
      email: 'mock@example.test',
      role: 'rw',
      is_active: true,
      date_joined: '2026-01-01T00:00:00Z',
    }),
    getConfigViewApiV1ConfigGetMockHandler({
      admin_user_exists: true,
      login_methods: ['local'],
      auth: { type: 'none' },
    }),
    getGetAvailableModelsViewApiV1AvailableModelsPostMockHandler(
      availableModels,
    ),
    getListCollectionsViewApiV1CollectionsGetMockHandler({
      items: [],
      pageResult: { count: 0, page_number: 1, page_size: 50 },
    }),
    getListChatsViewApiV1BotsBotIdChatsGetMockHandler({ items: [] }),
    getListBotsMockHandler(({ request }): BotList => {
      checkScenario();
      const query = new URL(request.url).searchParams;
      const page = Math.max(1, Number(query.get('page')) || 1);
      const pageSize = Math.max(1, Number(query.get('page_size')) || 50);
      const items = [...bots.values()];
      return {
        items: items.slice((page - 1) * pageSize, page * pageSize),
        pageResult: {
          count: items.length,
          page_number: page,
          page_size: pageSize,
        },
      };
    }),
    getCreateBotMockHandler(async ({ request }) => {
      checkScenario();
      const body = await request.json();
      if (!body.title?.trim()) reject(400, 'Title is required');
      const now = new Date().toISOString();
      const id = `mock-${randomUUID()}`;
      const bot: Bot = {
        ...body,
        id,
        type: body.type ?? 'agent',
        created: now,
        updated: now,
      };
      bots.set(id, bot);
      return bot;
    }),
    getGetBotMockHandler(({ params }) => requireBot(params.botId)),
    getUpdateBotMockHandler(async ({ params, request }) => {
      const old = requireBot(params.botId);
      const body = await request.json();
      const bot = {
        ...old,
        ...body,
        id: params.botId,
        updated: new Date().toISOString(),
      };
      bots.set(params.botId, bot);
      return bot;
    }),
    getDeleteBotMockHandler(({ params }) => {
      if (requireBot(params.botId).is_protected)
        reject(400, 'Protected Bot cannot be deleted');
      bots.delete(params.botId);
    }),
    // Generated shapes for other HTTP operations; business overrides go above.
    ...Object.values(generatedMocks).flatMap((getMocks) => getMocks()),
  ];
}
