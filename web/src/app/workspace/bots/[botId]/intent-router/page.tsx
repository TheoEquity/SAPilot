import {
  PageContainer,
  PageContent,
  PageHeader,
} from '@/components/page-container';
import { getTranslations } from 'next-intl/server';
import { IntentRouterEditor } from './intent-router-editor';

export default async function Page({
  params,
}: {
  params: Promise<{ botId: string }>;
}) {
  const { botId } = await params;
  const page_bot = await getTranslations('page_bot');

  return (
    <PageContainer>
      <PageHeader
        breadcrumbs={[
          {
            title: page_bot('metadata.title'),
            href: '/workspace/bots',
          },
          {
            title: page_bot('bot_settings'),
            href: `/workspace/bots/${botId}/settings`,
          },
          {
            title: page_bot('intent_router_title'),
          },
        ]}
      />
      <PageContent className="max-w-none pb-6">
        <IntentRouterEditor />
      </PageContent>
    </PageContainer>
  );
}
