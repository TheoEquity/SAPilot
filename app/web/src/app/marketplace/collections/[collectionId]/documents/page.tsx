import { PageContainer, PageContent } from '@/components/page-container';
import { getServerApi } from '@/lib/api/server';
import { parsePageParams, toJson } from '@/lib/utils';
import { notFound } from 'next/navigation';
import { CollectionHeader } from '../collection-header';
import { DocumentsTable } from './documents-table';

export default async function Page({
  params,
  searchParams,
}: Readonly<{
  params: Promise<{ collectionId: string }>;
  searchParams: Promise<{ page?: string; pageSize?: string; search?: string }>;
}>) {
  const { collectionId } = await params;
  const { page, pageSize, search } = await searchParams;
  const serverApi = await getServerApi();
  const pagination = parsePageParams({ page, pageSize });
  const [collectionRes, documentsRes] = await Promise.all([
    serverApi.marketplaceCollections.getMarketplaceCollectionApiV1MarketplaceCollectionsCollectionIdGet(
      encodeURIComponent(String(collectionId)),
    ),
    serverApi.marketplaceCollections.listMarketplaceCollectionDocumentsApiV1MarketplaceCollectionsCollectionIdDocumentsGet(
      encodeURIComponent(collectionId),
      {
        page: pagination.page,
        page_size: pagination.pageSize,
        sort_by: 'created',
        sort_order: 'desc',
        search,
      },
    ),
  ]);

  const documents = toJson(documentsRes.data.items || []);
  const collection = toJson(collectionRes.data);

  if (!collection) {
    notFound();
  }

  return (
    <PageContainer>
      <CollectionHeader collection={collection} />
      <PageContent>
        <DocumentsTable
          collection={collection}
          data={documents}
          pageCount={documentsRes.data.total_pages ?? undefined}
        />
      </PageContent>
    </PageContainer>
  );
}
