import {
  PageContainer,
  PageContent,
  PageHeader,
} from '@/components/page-container';
import { getTranslations } from 'next-intl/server';
import { SkillEditor } from '../skill-editor';

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
            title: page_bot('skills_title'),
            href: `/workspace/bots/${botId}/skills`,
          },
          {
            title: page_bot('new_skill'),
          },
        ]}
      />
      <PageContent className="max-w-none pb-6">
        <SkillEditor />
      </PageContent>
    </PageContainer>
  );
}
