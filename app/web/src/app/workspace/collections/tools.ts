import { DocumentStatus } from '@/api/generated/models';

export const getDocumentStatusColor = (status?: DocumentStatus) => {
  const data: {
    [key in Exclude<DocumentStatus, null>]: string;
  } = {
    [DocumentStatus.PENDING]: 'text-muted-foreground',
    [DocumentStatus.RUNNING]: 'text-muted-foreground',
    [DocumentStatus.COMPLETE]: 'text-accent-foreground',
    [DocumentStatus.UPLOADED]: 'text-muted-foreground',
    [DocumentStatus.FAILED]: 'text-red-500',
    [DocumentStatus.EXPIRED]: 'text-muted-foreground line-through',
    [DocumentStatus.DELETED]: 'text-muted-foreground line-through',
    [DocumentStatus.DELETING]: 'text-muted-foreground line-through',
  };
  return status ? data[status] : 'text-muted-foreground';
};
