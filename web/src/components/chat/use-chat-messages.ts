'use client';

import { ChatDetails, ChatMessage, Feedback, Reference } from '@/api';
import { useBotContext } from '@/components/providers/bot-provider';
import { apiClient } from '@/lib/api/client';
import { logger } from '@/lib/logger';
import { useWebSocket } from 'ahooks';
import { useLocale, useTranslations } from 'next-intl';
import { useParams } from 'next/navigation';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { animateScroll as scroll } from 'react-scroll';
import type { ChatInputSubmitParams } from './chat-input';

export const useChatMessages = (chat: ChatDetails) => {
  const { chatRename } = useBotContext();
  const { botId, chatId } = useParams<{ botId: string; chatId: string }>();
  const locale = useLocale();
  const pageChat = useTranslations('page_chat');
  const [messages, setMessages] = useState<Array<Array<ChatMessage>>>(
    chat?.history || [],
  );
  // const [messagesLoading, setMessagesLoading] = useState<boolean>(false);

  const [loading, setLoading] = useState<boolean>(false);
  const activeResponse = useRef<{ id?: string; socket: WebSocket } | null>(
    null,
  );
  const interruptResponse = (socket: WebSocket) => {
    const response = activeResponse.current;
    if (!response || response.socket !== socket) return false;
    activeResponse.current = null;
    setLoading(false);
    const error: ChatMessage = {
      id: response.id,
      type: 'error',
      role: 'ai',
      data: pageChat('connection_interrupted'),
      timestamp: Math.floor(Date.now() / 1000),
    };
    setMessages((msgs) => {
      const index = msgs.findLastIndex((parts) =>
        parts.some((part) => part.id === response.id && part.role === 'ai'),
      );
      return index < 0
        ? [...msgs, [error]]
        : msgs.map((parts, i) => (i === index ? [...parts, error] : parts));
    });
    return true;
  };
  const { protocol, host } = useMemo(() => {
    if (typeof window !== 'undefined') {
      return {
        protocol: window.location.protocol === 'http:' ? 'ws://' : 'wss://',
        host: window.location.host,
      };
    } else {
      return {
        protocol: 'ws://',
        host: 'localhost:8000',
      };
    }
  }, []);

  const { sendMessage, readyState, disconnect, connect } = useWebSocket(
    `${protocol}${host}${process.env.NEXT_PUBLIC_BASE_PATH || ''}/api/v1/bots/${botId}/chats/${chatId}/connect`,
    {
      onMessage: (message, socket) => {
        let fragment: ChatMessage;
        try {
          fragment = JSON.parse(message.data) as ChatMessage;
        } catch (error) {
          logger.error('chat.response.invalid', { chat_id: chatId, error });
          throw error;
        }
        if (fragment.type === 'start') {
          activeResponse.current = { id: fragment.id, socket };
          logger.info('chat.response.started', {
            chat_id: chatId,
            message_id: fragment.id,
            status: 'started',
          });
          setLoading(true);
        }
        if (fragment.type === 'stop') {
          activeResponse.current = null;
          logger.info('chat.response.completed', {
            chat_id: chatId,
            message_id: fragment.id,
            status: 'success',
          });
          setLoading(false);
          if (chatRename && chat) {
            chatRename(chat);
          }
        }
        if (fragment.id === 'error' || fragment.type === 'error') {
          activeResponse.current = null;
          setLoading(false);
          // The server error is rendered in the chat; it is a handled failure.
          logger.warn('chat.response.failed', {
            chat_id: chatId,
            status: 'failed',
          });
        }
        setMessages((msgs) => {
          const partsIndex = msgs.findLastIndex((parts) => {
            return Boolean(
              parts.find(
                (part) =>
                  part.id !== 'error' &&
                  part.id === fragment.id &&
                  part.role === 'ai',
              ),
            );
          });
          const parts = partsIndex > -1 ? msgs[partsIndex] : undefined;

          if (parts) {
            if (fragment.type === 'stop') {
              parts.push({
                id: fragment.id,
                type: 'references',
                references: Array.isArray(fragment.data)
                  ? (fragment.data as Reference[])
                  : [],
                data: '',
                role: 'ai',
                skill_id: fragment.skill_id,
              });
            }
            if (fragment.type === 'start') {
              parts.push({
                ...fragment,
                type: 'start',
                data: '',
              });
            } else if (fragment.type === 'message') {
              const part = parts.find((p) => p.type === 'message');
              if (part) {
                part.data = (part.data || '') + fragment.data;
              } else {
                parts.push(fragment);
              }
            } else {
              const part = parts.find(
                (p) => fragment.part_id && fragment.part_id === p.part_id,
              );
              if (part) {
                part.data = (part.data || '') + fragment.data;
              } else {
                parts.push(fragment);
              }
            }
            msgs[partsIndex] = [...parts];
          } else {
            msgs.push([
              {
                ...fragment,
                role: 'ai',
              },
            ]);
          }
          return [...msgs];
        });
      },
      onError: (_event, socket) => {
        interruptResponse(socket);
        logger.warn('chat.connection.failed', {
          chat_id: chatId,
          status: 'failed',
        });
      },
      onClose: (event, socket) => {
        const interrupted = interruptResponse(socket);
        if (interrupted || event.code === 1006) {
          logger.warn('chat.connection.closed', {
            chat_id: chatId,
            close_code: event.code,
            status: 'failed',
          });
        }
      },
    },
  );

  const handleSendMessage = useCallback(
    (params: ChatInputSubmitParams) => {
      const timestamp = Math.floor(new Date().getTime() / 1000);
      const part: ChatMessage = {
        type: 'message',
        role: 'human',
        data: params.query || ' ',
        files: params.files,
        timestamp,
      };
      setMessages((msgs) => {
        msgs?.push([part]);
        return [...msgs];
      });

      try {
        sendMessage(JSON.stringify(params));
      } catch (error) {
        logger.error('chat.message.failed', { chat_id: chatId, error });
        throw error;
      }
      logger.info('chat.message.submitted', {
        chat_id: chatId,
        status: 'submitted',
        file_count: params.files?.length || 0,
      });
    },
    [sendMessage, chatId],
  );

  const handleFaqChoice = useCallback(
    (action: string, label: string) => {
      const timestamp = Math.floor(new Date().getTime() / 1000);
      const part: ChatMessage = {
        type: 'message',
        role: 'human',
        data: label,
        timestamp,
      };
      setMessages((msgs) => {
        msgs?.push([part]);
        return [...msgs];
      });

      try {
        sendMessage(
          JSON.stringify({
            query: label,
            action,
            collections: [],
            completion: null,
            web_search_enabled: false,
            language: locale,
            files: [],
          }),
        );
      } catch (error) {
        logger.error('chat.message.failed', { chat_id: chatId, error });
        throw error;
      }
      logger.info('chat.message.submitted', {
        chat_id: chatId,
        status: 'submitted',
      });
    },
    [locale, sendMessage, chatId],
  );

  const hanldeMessageFeedback = useCallback(
    async (part: ChatMessage, feedback: Feedback) => {
      if (!botId || !chatId || !part.id) return;
      const res =
        await apiClient.defaultApi.botsBotIdChatsChatIdMessagesMessageIdPost({
          botId,
          chatId,
          messageId: part.id,
          feedback,
        });
      if (res.status === 200) {
        setMessages((msgs) => {
          const parts = msgs.find((items) =>
            items.find((p) => p.id === part.id && p.type === 'references'),
          );
          const feedbackPart = parts?.find((p) => p.type === 'references');
          if (feedbackPart) {
            feedbackPart.feedback = feedback;
          }
          return [...msgs];
        });
      }
    },
    [botId, chatId],
  );

  const handleCancel = useCallback(() => {
    activeResponse.current = null;
    logger.info('chat.message.cancelled', {
      chat_id: chatId,
      status: 'cancelled',
    });
    disconnect();
    connect();
    setLoading(false);
  }, [connect, disconnect, chatId]);

  useEffect(() => {
    if (loading) {
      scroll.scrollToBottom({ duration: 0 });
    }
  }, [messages, chat, loading]);

  useEffect(() => {
    scroll.scrollToBottom({ duration: 0 });
  }, []);

  /**
   * render in server for the first time
   * should delete for production
   */
  // const loadMessages = useCallback(async () => {
  //   setMessagesLoading(true);
  //   const res = await apiClient.defaultApi.botsBotIdChatsChatIdGet({
  //     botId,
  //     chatId,
  //   });
  //   setMessages(res.data.history || []);
  //   setMessagesLoading(false);
  // }, [botId, chatId]);

  // useEffect(() => {
  //   loadMessages();
  // }, [loadMessages]);

  return {
    messages,
    loading,
    readyState,
    handleSendMessage,
    handleFaqChoice,
    hanldeMessageFeedback,
    handleCancel,
  };
};
