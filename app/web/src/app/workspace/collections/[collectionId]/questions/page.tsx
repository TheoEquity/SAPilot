import {
  PageContainer,
  PageContent,
  PageHeader,
} from '@/components/page-container';
import { getServerApi } from '@/lib/api/server';
import { getTranslations } from 'next-intl/server';
import { CollectionHeader } from '../collection-header';
import { QuestionSetList } from './question-set-list';

export default async function Page({
  params,
}: {
  params: Promise<{ collectionId: string }>;
}) {
  const { collectionId } = await params;
  const serverApi = await getServerApi();
  const page_question_set = await getTranslations('page_question_set');
  const page_collections = await getTranslations('page_collections');

  const [questionSetsRes] = await Promise.all([
    serverApi.evaluation.listQuestionSetsApiV1QuestionSetsGet({
      collection_id: collectionId,
      page: 1,
      page_size: 100,
    }),
  ]);

  return (
    <PageContainer>
      <PageHeader
        breadcrumbs={[
          {
            title: page_collections('metadata.title'),
            href: '/workspace/collections',
          },
          { title: page_question_set('metadata.title') },
        ]}
      />
      <CollectionHeader />
      <PageContent>
        <QuestionSetList questionSets={questionSetsRes.data.items || []} />
      </PageContent>
    </PageContainer>
  );
}
