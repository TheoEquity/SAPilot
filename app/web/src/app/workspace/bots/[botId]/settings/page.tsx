import {
  PageContainer,
  PageContent,
  PageHeader,
} from '@/components/page-container';

import { getTranslations } from 'next-intl/server';
import { BotForm } from '../bot-form';

export default async function Page() {
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
          },
        ]}
      />
      <PageContent>
        <BotForm />
      </PageContent>
    </PageContainer>
  );
}
