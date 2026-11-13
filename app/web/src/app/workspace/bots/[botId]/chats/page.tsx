import type { Chat } from '@/api/generated/models';
import {
  PageContainer,
  PageContent,
  PageHeader,
} from '@/components/page-container';
import { getServerApi } from '@/lib/api/server';
import _ from 'lodash';
import { getTranslations } from 'next-intl/server';
import { redirect } from 'next/navigation';

export default async function Page({
  params,
}: Readonly<{
  params: Promise<{ botId: string }>;
}>) {
  const apiServer = await getServerApi();
  const page_chat = await getTranslations('page_chat');
  const { botId } = await params;
  const chatsRes = await apiServer.chats.listChatsViewApiV1BotsBotIdChatsGet(
    encodeURIComponent(botId),
    { page: 1, page_size: 1 },
  );

  const chat: Chat | undefined = _.first(chatsRes.data.items || []);

  if (chat) {
    redirect(`/workspace/bots/${botId}/chats/${chat.id}`);
  }

  return (
    <PageContainer>
      <PageHeader
        breadcrumbs={[{ title: page_chat('metadata.title') }]}
        extra=""
      />
      <PageContent></PageContent>
    </PageContainer>
  );
}
