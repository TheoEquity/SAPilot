'use client';

import { ChatDetails } from '@/api';
import { ReadyState } from 'ahooks/lib/useWebSocket';
import { motion } from 'framer-motion';
import _ from 'lodash';
import { ChatInput } from './chat-input';
import { MessagePartsAi } from './message-parts-ai';
import { MessagePartsUser } from './message-parts-user';
import { useChatMessages } from './use-chat-messages';

export const ChatMessages = ({ chat }: { chat: ChatDetails }) => {
  const {
    messages,
    loading,
    readyState,
    handleSendMessage,
    handleFaqChoice,
    hanldeMessageFeedback,
    handleCancel,
  } = useChatMessages(chat);

  return (
    <div className="flex flex-col gap-6 pb-70">
      {messages.map((parts, index) => {
        const isAI = parts.some((part) => part.role === 'ai');
        // Ensure role is properly set for safety
        const safeParts = parts.map((part) => ({
          ...part,
          role: part.role || (isAI ? 'ai' : 'human'),
        }));
        const isLoading = loading && index + 1 === messages.length;
        const isAIPending =
          isLoading &&
          parts.filter((p) => p.type !== 'start').length === 0 &&
          isAI;

        return (
          <motion.div
            key={index}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{
              duration: 0.3,
              ease: 'easeIn',
            }}
          >
            {isAI ? (
              <MessagePartsAi
                pending={isAIPending}
                loading={isLoading}
                parts={safeParts}
                hanldeMessageFeedback={hanldeMessageFeedback}
                onFaqChoice={handleFaqChoice}
              />
            ) : (
              <MessagePartsUser parts={safeParts} />
            )}
          </motion.div>
        );
      })}
      <ChatInput
        chat={chat}
        welcome={_.isEmpty(messages)}
        onSubmit={handleSendMessage}
        disabled={readyState !== ReadyState.Open}
        loading={loading}
        onCancel={handleCancel}
      />
    </div>
  );
};
