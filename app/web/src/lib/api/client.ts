'use client';

import { getApiKeys } from '@/api/generated/api-keys/api-keys';
import { getAuth } from '@/api/generated/auth/auth';
import { getBots } from '@/api/generated/bots/bots';
import { getChats } from '@/api/generated/chats/chats';
import { getCollections } from '@/api/generated/collections/collections';
import { getDefaultModels } from '@/api/generated/default-models/default-models';
import { getDocuments } from '@/api/generated/documents/documents';
import { getEvaluation } from '@/api/generated/evaluation/evaluation';
import { getExport } from '@/api/generated/export/export';
import { getGraph } from '@/api/generated/graph/graph';
import { getLlmModels } from '@/api/generated/llm-models/llm-models';
import { getLlmProviders } from '@/api/generated/llm-providers/llm-providers';
import { getMarketplaceCollections } from '@/api/generated/marketplace-collections/marketplace-collections';
import { getMarketplace } from '@/api/generated/marketplace/marketplace';
import { getPrompts } from '@/api/generated/prompts/prompts';
import { getQuotas } from '@/api/generated/quotas/quotas';
import { getSearch } from '@/api/generated/search/search';
import { getSettings } from '@/api/generated/settings/settings';
import { getUsers } from '@/api/generated/users/users';
import axios from 'axios';

import { toast } from 'sonner';
import { attachRequestLogging } from './logging';

const request = axios.create({
  baseURL: `${process.env.NEXT_PUBLIC_BASE_PATH || ''}/api/v1`,
  timeout: 1000 * 5,
});

attachRequestLogging(request);

request.interceptors.response.use(
  function (response) {
    // Any status code that lie within the range of 2xx cause this function to trigger
    // Do something with response data
    return response;
  },
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  function (err: any) {
    let bizMessage: string | undefined;

    if (typeof err.response?.data?.detail === 'string') {
      bizMessage = err.response.data.detail;
    } else if (typeof err.response?.data?.detail?.message === 'string') {
      bizMessage = err.response.data.detail.message;
    } else {
      bizMessage = err.response?.data?.message;
    }

    if (bizMessage) {
      toast.error(bizMessage);
    }
    return Promise.reject(err);
  },
);

export const apiClient = {
  apiKeys: getApiKeys(request),
  auth: getAuth(request),
  bots: getBots(request),
  chats: getChats(request),
  collections: getCollections(request),
  defaultModels: getDefaultModels(request),
  documents: getDocuments(request),
  evaluation: getEvaluation(request),
  export: getExport(request),
  graph: getGraph(request),
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
