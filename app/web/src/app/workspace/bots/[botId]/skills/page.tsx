import {
  PageContainer,
  PageContent,
  PageHeader,
  PageTitle,
} from '@/components/page-container';
import { Button } from '@/components/ui/button';
import { getTranslations } from 'next-intl/server';
import Link from 'next/link';
import { SkillList } from './skill-list';

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
          },
        ]}
      />
      <PageContent className="flex items-center justify-between gap-4">
        <div>
          <PageTitle>{page_bot('skills_title')}</PageTitle>
          <p className="text-muted-foreground text-sm">
            {page_bot('skills_description')}
          </p>
        </div>
        <Button asChild>
          <Link href={`/workspace/bots/${botId}/skills/new`}>
            {page_bot('new_skill')}
          </Link>
        </Button>
      </PageContent>
      <PageContent className="pb-6">
        <SkillList />
      </PageContent>
    </PageContainer>
  );
}
