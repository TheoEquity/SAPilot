import { ChatMessage } from '@/api';
import { Markdown } from '@/components/markdown';
import { FileImage, UserRound } from 'lucide-react';
import { MessageTimestamp } from './message-timestamp';

const resolvePreviewUrl = (url?: string) => {
  if (!url) return undefined;
  if (!url.startsWith('/')) return url;
  return `${process.env.NEXT_PUBLIC_BASE_PATH || ''}${url}`;
};

export const MessagePartsUser = ({ parts }: { parts: ChatMessage[] }) => {
  const files = parts?.flatMap((part) => part.files || []).filter(Boolean);

  return (
    <div className="ml-auto flex w-max flex-row gap-4">
      <div className="flex max-w-sm flex-col gap-2 sm:max-w-lg md:max-w-2xl lg:max-w-3xl xl:max-w-4xl">
        <div className="bg-primary text-primary-foreground rounded-lg p-4 text-sm">
          <Markdown>{parts?.map((part) => part.data || '').join('')}</Markdown>
        </div>
        {files.length > 0 && (
          <div className="mt-1 flex flex-wrap items-center gap-2">
            {files.map((file, index) => {
              const previewUrl = resolvePreviewUrl(file.previewUrl);
              return (
                <a
                  key={`${file.id || file.name || 'file'}-${index}`}
                  href={previewUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="bg-muted text-muted-foreground hover:bg-muted/80 flex max-w-48 items-center gap-2 rounded-md border px-2 py-1 text-xs transition-colors"
                  onClick={(event) => {
                    if (!previewUrl) {
                      event.preventDefault();
                    }
                  }}
                  title={file.name || 'Attachment'}
                >
                  <FileImage className="size-4 shrink-0" />
                  <span className="truncate">{file.name || 'Attachment'}</span>
                </a>
              );
            })}
          </div>
        )}
        <MessageTimestamp parts={parts} />
      </div>
      <div>
        <div className="bg-muted text-muted-foreground flex size-12 flex-col justify-center rounded-full">
          <UserRound className="size-5 self-center" />
        </div>
      </div>
    </div>
  );
};
