import { Bot } from '@/api';
import {
  PageContainer,
  PageContent,
  PageDescription,
  PageHeader,
  PageTitle,
} from '@/components/page-container';

import { getServerApi } from '@/lib/api/server';
import { toJson } from '@/lib/utils';
import { Metadata } from 'next';
import { getTranslations } from 'next-intl/server';
import { BotList } from './bot-list';

export const dynamic = 'force-dynamic';

export async function generateMetadata(): Promise<Metadata> {
  const page_bots = await getTranslations('page_bot');
  return {
    title: page_bots('metadata.title'),
    description: page_bots('metadata.description'),
  };
}

export default async function Page() {
  const serverApi = await getServerApi();
  const page_bot = await getTranslations('page_bot');

  let bots: Bot[] = [];
  try {
    const res = await serverApi.defaultApi.botsGet({
      page: 1,
      pageSize: 100,
    });
    bots = res.data.items || [];
  } catch (err) {
    console.log(err);
  }

  return (
    <PageContainer>
      <PageHeader
        breadcrumbs={[{ title: page_bot('metadata.title') }]}
      />
      <PageContent>
        <PageTitle>{page_bot('metadata.title')}</PageTitle>
        <PageDescription>
          {page_bot('metadata.description')}
        </PageDescription>
        <BotList bots={toJson(bots)} />
      </PageContent>
    </PageContainer>
  );
}
