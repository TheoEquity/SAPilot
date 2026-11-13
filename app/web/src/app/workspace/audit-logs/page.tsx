import {
  PageContainer,
  PageContent,
  PageDescription,
  PageHeader,
  PageTitle,
} from '@/components/page-container';
import { getServerApi } from '@/lib/api/server';
import { parsePageParams, toJson } from '@/lib/utils';
import { getTranslations } from 'next-intl/server';
import { AuditLogTable, type AuditLogFilters } from './audit-log-table';

export default async function Page({
  searchParams,
}: {
  searchParams: Promise<AuditLogFilters>;
}) {
  const serverApi = await getServerApi();
  const page_audit_logs = await getTranslations('page_audit_logs');
  const {
    page,
    pageSize,
    sortBy = 'created',
    sortOrder = 'desc',
    apiName = '',
    startDate,
    endDate,
  } = await searchParams;

  let res;
  try {
    const pagination = parsePageParams({ page, pageSize });
    res = await serverApi.audit.listAuditLogsApiV1AuditLogsGet({
      api_name: apiName,
      sort_by: sortBy,
      sort_order: sortOrder ?? 'desc',
      start_date: startDate,
      end_date: endDate,
      page: pagination.page,
      page_size: pagination.pageSize,
    });
  } catch (err) {
    console.log(err);
  }

  const data = res?.data?.items || [];

  return (
    <PageContainer>
      <PageHeader
        breadcrumbs={[{ title: page_audit_logs('metadata.title') }]}
      />
      <PageContent>
        <PageTitle>{page_audit_logs('metadata.title')}</PageTitle>
        <PageDescription>
          {page_audit_logs('metadata.description')}
        </PageDescription>
        <AuditLogTable
          data={toJson(data)}
          pageCount={res?.data.total_pages || 1}
          urlPrefix="/workspace"
        />
      </PageContent>
    </PageContainer>
  );
}
