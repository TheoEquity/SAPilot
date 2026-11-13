'use client';

import { useCallback, useEffect, useState } from 'react';

import type { Bot, CollectionView as Collection } from '@/api/generated/models';
import { apiClient } from '@/lib/api/client';
import { createContext, useContext } from 'react';

type BotContextProps = {
  bot: Bot;
  collections: Collection[];
  loadBot: () => void;
  loadCollections: () => void;
};

const BotContext = createContext<BotContextProps>({
  bot: {},
  collections: [],
  loadBot: () => {},
  loadCollections: () => {},
});

export const useBotConfigContext = () => useContext(BotContext);

export const BotConfigProvider = ({
  bot: initBot,
  children,
}: {
  children?: React.ReactNode;
  bot: Bot;
}) => {
  const [bot, setBot] = useState<Bot>(initBot);
  const [collections, setCollections] = useState<Collection[]>([]);

  const loadBot = useCallback(async () => {
    if (!bot?.id) return;
    const res = await apiClient.bots.getBot(encodeURIComponent(String(bot.id)));
    setBot(res.data);
  }, [bot?.id]);

  const loadCollections = useCallback(async () => {
    const res =
      await apiClient.collections.listCollectionsViewApiV1CollectionsGet();
    setCollections(res.data.items || []);
  }, []);

  useEffect(() => {
    setBot(initBot);
  }, [initBot]);

  useEffect(() => {
    loadCollections();
  }, [loadCollections]);

  return (
    <BotContext.Provider value={{ bot, collections, loadBot, loadCollections }}>
      {children}
    </BotContext.Provider>
  );
};
