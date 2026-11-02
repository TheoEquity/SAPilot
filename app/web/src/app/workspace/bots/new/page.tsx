import {
  PageContainer,
  PageContent,
  PageHeader,
} from '@/components/page-container';

import { Bot } from '@/api';
import { getServerApi } from '@/lib/api/server';
import { toJson } from '@/lib/utils';
import { getTranslations } from 'next-intl/server';
import { BotCreateForm } from './bot-create-form';

export default async function Page({
  searchParams,
}: {
  searchParams: Promise<{ copyFrom?: string }>;
}) {
  const { copyFrom } = await searchParams;
  const page_bot = await getTranslations('page_bot');
  const serverApi = await getServerApi();
  let sourceBot: Bot | null = null;

  if (copyFrom) {
    try {
      const res = await serverApi.defaultApi.botsBotIdGet({ botId: copyFrom });
      sourceBot = toJson(res.data);
    } catch (err) {
      console.log(err);
    }
  }

  return (
    <PageContainer>
      <PageHeader
        breadcrumbs={[
          {
            title: page_bot('metadata.title'),
            href: '/workspace/bots',
          },
          {
            title: page_bot('new_bot'),
          },
        ]}
      />
      <PageContent>
        <BotCreateForm sourceBot={sourceBot} />
      </PageContent>
    </PageContainer>
  );
}
