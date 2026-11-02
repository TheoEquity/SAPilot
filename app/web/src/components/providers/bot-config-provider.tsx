'use client';

import { useCallback, useEffect, useState } from 'react';

import { Bot, Collection } from '@/api';
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
    const res = await apiClient.defaultApi.botsBotIdGet({
      botId: bot.id,
    });
    setBot(res.data);
  }, [bot?.id]);

  const loadCollections = useCallback(async () => {
    const res = await apiClient.defaultApi.collectionsGet();
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
