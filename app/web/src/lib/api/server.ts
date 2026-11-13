'use server';

import { getApiKeys } from '@/api/generated/api-keys/api-keys';
import { getAudit } from '@/api/generated/audit/audit';
import { getBots } from '@/api/generated/bots/bots';
import { getChats } from '@/api/generated/chats/chats';
import { getCollections } from '@/api/generated/collections/collections';
import { getConfig } from '@/api/generated/config/config';
import { getDocuments } from '@/api/generated/documents/documents';
import { getEvaluation } from '@/api/generated/evaluation/evaluation';
import { getLlmModels } from '@/api/generated/llm-models/llm-models';
import { getLlmProviders } from '@/api/generated/llm-providers/llm-providers';
import { getMarketplaceCollections } from '@/api/generated/marketplace-collections/marketplace-collections';
import { getMarketplace } from '@/api/generated/marketplace/marketplace';
import { getPrompts } from '@/api/generated/prompts/prompts';
import { getQuotas } from '@/api/generated/quotas/quotas';
import { getSearch } from '@/api/generated/search/search';
import { getSettings } from '@/api/generated/settings/settings';
import { getUsers } from '@/api/generated/users/users';
import { getLocale } from '@/services/cookies';
import axios from 'axios';
import { cookies } from 'next/headers';
import { attachRequestLogging } from './logging';

const request = axios.create({
  baseURL:
    (process.env.API_SERVER_ENDPOINT || 'http://localhost:8000') +
    (process.env.API_SERVER_BASE_PATH || '/api/v1'),
  timeout: 1000 * 15,
});

request.interceptors.request.use(
  async (config) => {
    const lang = await getLocale();
    const allCookies = (await cookies())
      .getAll()
      .map((item) => `${item.name}=${item.value}`)
      .join('; ');
    Object.assign(config.headers, {
      Lang: lang,
      Cookie: allCookies,
    });
    return config;
  },
  function (error) {
    return Promise.reject(error);
  },
);

attachRequestLogging(request);

const api = {
  apiKeys: getApiKeys(request),
  audit: getAudit(request),
  bots: getBots(request),
  chats: getChats(request),
  collections: getCollections(request),
  config: getConfig(request),
  documents: getDocuments(request),
  evaluation: getEvaluation(request),
  llmModels: getLlmModels(request),
  llmProviders: getLlmProviders(request),
  marketplace: getMarketplace(request),
  marketplaceCollections: getMarketplaceCollections(request),
  prompts: getPrompts(request),
  quotas: getQuotas(request),
  search: getSearch(request),
  settings: getSettings(request),
  users: getUsers(request),
};

export const getServerApi = async () => {
  return api;
};
