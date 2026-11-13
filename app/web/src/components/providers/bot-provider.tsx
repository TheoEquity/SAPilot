'use client';

import { apiClient } from '@/lib/api/client';
import { logger } from '@/lib/logger';
import { useCallback, useEffect, useState } from 'react';

import type {
  Bot,
  Chat,
  ChatDetails,
  CollectionView as Collection,
  ModelSpec,
} from '@/api/generated/models';
import { useLocale } from 'next-intl';
import { useParams, usePathname, useRouter } from 'next/navigation';
import { createContext, useContext } from 'react';
import { toast } from 'sonner';

export type ProviderModels = {
  label?: string | null;
  name?: string | null;
  models?: ModelSpec[] | null;
}[];

type BotContextProps = {
  workspace?: boolean;
  bot?: Bot;
  chats: Chat[];
  mention: boolean;
  collections: Collection[];
  providerModels: ProviderModels;
  chatDelete?: (chat: Chat) => void;
  chatCreate?: () => void;
  chatsReload?: () => void;
  chatRename?: (chat: Chat | ChatDetails) => void;
};

const BotContext = createContext<BotContextProps>({
  chats: [],
  mention: true,
  collections: [],
  providerModels: [],
});

export const useBotContext = () => useContext(BotContext);

export const BotProvider = ({
  bot: initBot,
  chats: initChats,
  mention = true,
  workspace,
  children,
}: {
  workspace: boolean;
  bot?: Bot;
  chats: Chat[];
  mention?: boolean;
  children?: React.ReactNode;
}) => {
  const [bot, setBot] = useState<Bot | undefined>(initBot);
  const [chats, setChats] = useState<Chat[]>(initChats || []);
  const params = useParams();
  const pathname = usePathname();
  const router = useRouter();
  const locale = useLocale();
  const botId = typeof params.botId === 'string' ? params.botId : undefined;
  const isInChatInterface =
    pathname.includes('/bots/') && pathname.includes('/chats');

  const [collections, setCollections] = useState<Collection[]>([]);
  const [providerModels, setProviderModels] = useState<ProviderModels>([]);

  const loadData = useCallback(async () => {
    const [modelRes, collectionsRes] = await Promise.all([
      apiClient.llmModels.getAvailableModelsViewApiV1AvailableModelsPost({
        tag_filters: [{ operation: 'AND', tags: ['enable_for_agent'] }],
      }),
      apiClient.collections.listCollectionsViewApiV1CollectionsGet(),
    ]);

    const items = modelRes.data.items?.map((m) => {
      return {
        label: m.label,
        name: m.name,
        models: m.completion,
      };
    });
    setCollections(collectionsRes.data.items || []);
    setProviderModels(items || []);
  }, []);

  const chatsReload = useCallback(async () => {
    if (!bot?.id) {
      setChats([]);
      return;
    }
    const chatsRes = await apiClient.chats.listChatsViewApiV1BotsBotIdChatsGet(
      encodeURIComponent(String(bot.id)),
    );
    setChats(chatsRes.data.items || []);
  }, [bot?.id]);

  const loadCurrentBot = useCallback(async () => {
    if (!botId) {
      setBot(initBot);
      setChats(initChats || []);
      return;
    }

    const [botRes, chatsRes] = await Promise.all([
      apiClient.bots.getBot(encodeURIComponent(String(botId))),
      apiClient.chats.listChatsViewApiV1BotsBotIdChatsGet(
        encodeURIComponent(String(botId)),
      ),
    ]);

    setBot(botRes.data);
    setChats(chatsRes.data.items || []);
  }, [botId, initBot, initChats]);

  const chatDelete = useCallback(
    async (chat: Chat) => {
      if (!chat.bot_id || !chat.id) return;
      await apiClient.chats.deleteChatViewApiV1BotsBotIdChatsChatIdDelete(
        encodeURIComponent(chat.bot_id),
        encodeURIComponent(chat.id),
      );

      if (params.chatId === chat.id) {
        const item = chats?.find((c) => c.id !== chat.id);
        let url = '';
        if (item) {
          url = `/bots/${bot?.id}/chats/${item.id}`;
        } else {
          url = `/bots/${bot?.id}/chats`;
        }
        if (workspace) {
          url = '/workspace' + url;
        }
        router.push(url);
      }
      chatsReload();
    },
    [bot?.id, chats, chatsReload, params.chatId, router, workspace],
  );

  const chatRename = useCallback(
    async (chat: Chat) => {
      if (chat.title !== 'New Chat' || !chat.id || !chat.bot_id) return;
      try {
        const titleRes =
          await apiClient.chats.generateChatTitleViewApiV1BotsBotIdChatsChatIdTitlePost(
            encodeURIComponent(String(chat.bot_id)),
            encodeURIComponent(String(chat.id)),
            {
              language: locale,
            },
            undefined,
            { validateStatus: (status) => status === 200 || status === 400 },
          );
        if (titleRes.status === 400) {
          const errorBody = titleRes.data as unknown as {
            detail?: string | { error_code?: string; message?: string };
            message?: string;
          };
          const { detail } = errorBody;
          if (
            typeof detail === 'object' &&
            detail?.error_code === 'LLM_MODEL_NOT_FOUND' &&
            detail.message === 'Background task default model not configured'
          ) {
            return;
          }
          const message =
            typeof detail === 'string'
              ? detail
              : (detail?.message ?? errorBody.message);
          if (message) toast.error(message);
          throw new Error(message || 'Chat title generation failed');
        }
        const title = titleRes.data.title;
        if (title) {
          await apiClient.chats.updateChatViewApiV1BotsBotIdChatsChatIdPut(
            encodeURIComponent(String(chat.bot_id)),
            encodeURIComponent(String(chat.id)),
            {
              title,
            },
          );
          await chatsReload();
        }
      } catch (error) {
        // Automatic naming must not turn a completed answer into a page error.
        logger.warn('chat.title.failed', {
          chat_id: chat.id,
          stage: 'chat.title',
          status: 'failed',
          error,
        });
      }
    },
    [chatsReload, locale],
  );

  const chatCreate = useCallback(async () => {
    if (!bot?.id) return;
    const res = await apiClient.chats.createChatViewApiV1BotsBotIdChatsPost(
      encodeURIComponent(bot.id),
    );

    if (res.data.id) {
      let url = `/bots/${bot.id}/chats/${res.data.id}`;
      if (workspace) {
        url = '/workspace' + url;
      }
      router.push(url);
      chatsReload();
    }
  }, [bot?.id, chatsReload, router, workspace]);

  useEffect(() => {
    if (isInChatInterface && bot?.id && chats.length === 0) {
      chatCreate();
    }
  }, [bot?.id, chatCreate, chats, isInChatInterface]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  useEffect(() => {
    loadCurrentBot();
  }, [loadCurrentBot]);

  return (
    <BotContext.Provider
      value={{
        mention,
        workspace,
        bot,
        chats,
        collections,
        providerModels,
        chatDelete,
        chatCreate,
        chatsReload,
        chatRename,
      }}
    >
      {children}
    </BotContext.Provider>
  );
};
