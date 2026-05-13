'use client';

import { ChatMessage } from '@/api';
import { ImagePreview, Markdown } from '@/components/markdown';
import { FileImage, UserRound } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { MessageTimestamp } from './message-timestamp';

const resolvePreviewUrl = (url?: string) => {
  if (!url) return undefined;
  if (!url.startsWith('/')) return url;
  return `${process.env.NEXT_PUBLIC_BASE_PATH || ''}${url}`;
};

const isImageAttachment = (name?: string) =>
  /\.(png|jpe?g|webp|gif|bmp)$/i.test(name || '');

const ChatAttachmentImage = ({
  name,
  previewUrl,
  className,
}: {
  name?: string;
  previewUrl: string;
  className: string;
}) => {
  const [imageUrl, setImageUrl] = useState<string>();

  const getImageSrc = useCallback(async () => {
    const response = await fetch(previewUrl);
    if (!response.ok) return;
    const blob = await response.blob();
    setImageUrl(URL.createObjectURL(blob));
  }, [previewUrl]);

  useEffect(() => {
    getImageSrc();
  }, [getImageSrc]);

  useEffect(() => {
    return () => {
      if (imageUrl) {
        URL.revokeObjectURL(imageUrl);
      }
    };
  }, [imageUrl]);

  const content = (
    <span className={className} title={name || 'Attachment'}>
      <FileImage className="size-4 shrink-0" />
      <span className="truncate">{name || 'Attachment'}</span>
    </span>
  );

  if (!imageUrl) return content;

  return (
    <ImagePreview imageUrl={imageUrl} alt={name || 'Attachment'}>
      {content}
    </ImagePreview>
  );
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
              const canPreview = previewUrl && isImageAttachment(file.name);
              const className =
                'bg-muted text-muted-foreground hover:bg-muted/80 flex max-w-48 items-center gap-2 rounded-md border px-2 py-1 text-xs transition-colors';

              if (canPreview) {
                return (
                  <ChatAttachmentImage
                    key={`${file.id || file.name || 'file'}-${index}`}
                    name={file.name}
                    previewUrl={previewUrl}
                    className={className}
                  />
                );
              }

              return (
                <span
                  key={`${file.id || file.name || 'file'}-${index}`}
                  className={className}
                  title={file.name || 'Attachment'}
                >
                  <FileImage className="size-4 shrink-0" />
                  <span className="truncate">{file.name || 'Attachment'}</span>
                </span>
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
