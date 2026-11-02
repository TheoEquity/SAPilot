import { Reference } from '@/api';
import { CustomImage, Markdown } from '@/components/markdown';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Drawer,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
  DrawerTrigger,
} from '@/components/ui/drawer';
import _ from 'lodash';
import { useTranslations } from 'next-intl';
import { MessageCollapseContent } from './message-collapse-content';

const extractAssetUrls = (text: string) => {
  const urls: string[] = [];
  const pattern = /!\[[^\]]*\]\((asset:\/\/[^\s)]+)\)/g;
  let match;
  while ((match = pattern.exec(text)) !== null) {
    urls.push(match[1]);
  }
  return urls;
};

const cleanMarkdownCell = (text: string) => {
  return text
    .replace(/!\[[^\]]*\]\(asset:\/\/[^\s)]+\)/g, '')
    .replace(/\\\*/g, '*')
    .trim();
};

const parseFaqRows = (text: string) => {
  return text
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line.startsWith('|') && !/^\|\s*-+/.test(line))
    .map((line) => {
      const cells = line
        .slice(1, line.endsWith('|') ? -1 : undefined)
        .split('|')
        .map((cell) => cell.trim());
      return {
        cells,
        text: cleanMarkdownCell(cells.join(' ')),
        images: extractAssetUrls(line),
      };
    })
    .filter((row) => row.text || row.images.length > 0);
};

const FaqReferenceContent = ({ reference }: { reference: Reference }) => {
  const rows = parseFaqRows(reference.text || '');
  const contentRows = rows.filter((row) => {
    const firstCell = row.cells[0] || '';
    return !firstCell.startsWith('FAQ');
  });

  return (
    <div className="space-y-3">
      {contentRows.map((row, index) => (
        <div
          className="grid gap-3 rounded-md border p-3 md:grid-cols-[minmax(0,1.25fr)_minmax(220px,0.75fr)]"
          key={index}
        >
          <div className="whitespace-pre-wrap break-words text-sm leading-6">
            {row.text}
          </div>
          <div className="space-y-2">
            {row.images.length > 0 ? (
              row.images.map((src) => <CustomImage key={src} src={src} />)
            ) : (
              <div className="text-muted-foreground rounded-md border border-dashed p-3 text-center text-xs">
                无配图
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
};

export const MessageReference = ({
  references,
}: {
  references: Reference[];
}) => {
  const page_chat = useTranslations('page_chat');
  const primaryReferences = references.filter(
    (reference) =>
      reference.metadata?.type !== 'list_collections' &&
      reference.metadata?.type !== 'search_chat_files',
  );
  const visibleReferences = _.isEmpty(primaryReferences)
    ? references.slice(0, 1)
    : primaryReferences.slice(0, 1);
  const getReferenceTitle = (reference: Reference, index: number) => {
    const metadata = reference.metadata || {};
    const title = metadata.faq_id
      ? `${metadata.faq_id}${metadata.faq_title ? ` ${metadata.faq_title}` : ''}`
      : metadata.document_source ||
        metadata.source ||
        metadata.query ||
        _.truncate(reference.text, { length: 30 });
    return `${index + 1}. ${title}`;
  };

  const getReferenceSource = (reference: Reference) => {
    const metadata = reference.metadata || {};
    return [
      metadata.document_source || metadata.source,
      metadata.faq_id,
      metadata.faq_title,
    ]
      .filter(Boolean)
      .join(' / ');
  };

  return (
    <Drawer direction="right" handleOnly={true}>
      <DrawerTrigger asChild>
        <Button variant="ghost" size="icon" className="cursor-pointer">
          <Badge
            className="h-5 min-w-5 rounded-full px-1 font-mono tabular-nums"
            variant="destructive"
          >
            {visibleReferences?.length}
          </Badge>
        </Button>
      </DrawerTrigger>
      <DrawerContent className="flex sm:min-w-xl md:min-w-2xl">
        <DrawerHeader>
          <DrawerTitle className="font-bold">
            {page_chat('references')}
          </DrawerTitle>
        </DrawerHeader>
        <div className="overflow-auto px-4 pb-4 select-text">
          {visibleReferences?.map((reference: Reference, index) => {
            const source = getReferenceSource(reference);
            return (
              <MessageCollapseContent
                defaultOpen={true}
                key={index}
                title={
                  <div className="flex flex-row justify-between">
                    <div>{getReferenceTitle(reference, index)}</div>
                    <div className="text-muted-foreground ml-auto flex flex-row items-center gap-2 text-xs">
                      <span>
                        {_.startCase(
                          reference.metadata?.recall_type || reference.metadata?.type,
                        )}
                      </span>
                      <span>{(reference.score || 0).toFixed(2)}</span>
                    </div>
                  </div>
                }
              >
                {source && (
                  <div className="text-muted-foreground mb-3 rounded-md border bg-muted/30 px-3 py-2 text-xs">
                    来源：{source}
                  </div>
                )}
                {reference.metadata?.chunk_type === 'faq_entry' ? (
                  <FaqReferenceContent reference={reference} />
                ) : (
                  <Markdown>{reference.text}</Markdown>
                )}
              </MessageCollapseContent>
            );
          })}
        </div>
      </DrawerContent>
    </Drawer>
  );
};
