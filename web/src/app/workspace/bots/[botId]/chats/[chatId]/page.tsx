import { ChatMessages } from '@/components/chat/chat-messages';
import {
  PageContainer,
  PageContent,
  PageHeader,
} from '@/components/page-container';
import { getServerApi } from '@/lib/api/server';
import { Bot, Fingerprint } from 'lucide-react';
import { notFound } from 'next/navigation';

export default async function Page({
  params,
}: {
  params: Promise<{
    botId: string;
    chatId: string;
  }>;
}) {
  const { botId, chatId } = await params;
  const serverApi = await getServerApi();

  let chat;
  let bot;

  try {
    const [chatRes, botRes] = await Promise.all([
      serverApi.defaultApi.botsBotIdChatsChatIdGet({
        botId,
        chatId,
      }),
      serverApi.defaultApi.botsBotIdGet({
        botId,
      }),
    ]);
    chat = chatRes.data;
    bot = botRes.data;
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
  } catch (err) {
    notFound();
  }

  return (
    <PageContainer>
      <PageHeader
        content={
          <div className="flex min-w-0 items-center gap-4 text-sm">
            <div className="flex min-w-0 items-center gap-2 font-medium">
              <Bot className="size-4 shrink-0" />
              <span className="truncate">{bot.title}</span>
            </div>
            <div className="text-muted-foreground flex min-w-0 items-center gap-2">
              <Fingerprint className="size-4 shrink-0" />
              <span className="truncate">{bot.id}</span>
            </div>
          </div>
        }
      />
      <PageContent>
        <ChatMessages chat={chat} />
      </PageContent>
    </PageContainer>
  );
}
