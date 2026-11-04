import { ChatMessage, Feedback } from '@/api';
import { CopyToClipboard } from '@/components/copy-to-clipboard';
import { useBotContext } from '@/components/providers/bot-provider';
import { Card } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { cn } from '@/lib/utils';
import _ from 'lodash';
import { Bot, LoaderCircle } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { useMemo } from 'react';
import { MessageFeedback } from './message-feedback';
import { MessagePartAi } from './message-part-ai';
import { MessageReference } from './message-reference';
import { MessageTimestamp } from './message-timestamp';

export const MessagePartsAi = ({
  pending,
  loading,
  parts,
  hanldeMessageFeedback,
  onFaqChoice,
}: {
  pending: boolean;
  loading: boolean;
  parts: ChatMessage[];
  hanldeMessageFeedback: (part: ChatMessage, feedback: Feedback) => void;
  onFaqChoice: (action: string, label: string) => void;
}) => {
  const pageChat = useTranslations('page_chat');
  const { bot } = useBotContext();
  const references = useMemo(() => {
    const rawReferences = parts.findLast((part) => part.references)?.references || [];
    return rawReferences.filter((reference) => {
      const referenceType = reference.metadata?.type;
      return referenceType !== 'list_collections' && referenceType !== 'search_chat_files';
    });
  }, [parts]);
  const skillId = useMemo(
    () => parts.find((part) => part.skill_id)?.skill_id || '',
    [parts],
  );
  const skillLabel = useMemo(() => {
    if (!skillId) return '';
    const skills =
      ((bot?.config as { orchestration?: { skills?: { id?: string; name?: string; label?: string }[] } })
        ?.orchestration?.skills || []);
    const matchedSkill = skills.find((skill) => skill.id === skillId);
    return matchedSkill?.name || matchedSkill?.label || matchedSkill?.id || skillId;
  }, [bot?.config, skillId]);

  return (
    <div className="flex w-full flex-row gap-4">
      <div>
        <div className="bg-muted text-muted-foreground relative flex size-12 flex-col justify-center rounded-full">
          {loading && (
            <LoaderCircle className="absolute -left-1 size-14 animate-spin opacity-20" />
          )}
          <Bot className={cn('size-6 self-center')} />
        </div>
      </div>
      <div className="flex w-full max-w-sm flex-col gap-1 sm:max-w-lg md:max-w-2xl lg:max-w-3xl xl:max-w-4xl">
        {skillLabel ? (
          <div className="text-muted-foreground mb-1 flex items-center gap-2 text-xs">
            <span className="rounded-md border bg-muted px-2 py-0.5 font-mono">
              {pageChat('current_skill_label')}: {skillLabel}
            </span>
          </div>
        ) : null}
        <Card className="dark:border-card/0 block gap-0 px-4 py-4 text-sm">
          {pending ? (
            <div className="flex flex-row gap-2 py-2">
              <div className="bg-muted-foreground animate-caret-blink size-2 rounded-full delay-0"></div>
              <div className="bg-muted-foreground animate-caret-blink size-2 rounded-full delay-200"></div>
              <div className="bg-muted-foreground animate-caret-blink size-2 rounded-full delay-400"></div>
            </div>
          ) : (
            parts.map((part, index) => (
              <MessagePartAi
                key={`${index}-${part.id}`}
                part={part}
                loading={loading}
                onFaqChoice={onFaqChoice}
              />
            ))
          )}
        </Card>
        <div className="flex flex-row items-center gap-2">
          <MessageTimestamp parts={parts} className="mr-2" />
          <Separator
            orientation="vertical"
            className="data-[orientation=vertical]:h-4"
          />
          {!_.isEmpty(references) && (
            <>
              <MessageReference references={references} />
              <Separator
                orientation="vertical"
                className="data-[orientation=vertical]:h-4"
              />
            </>
          )}
          <MessageFeedback
            parts={parts}
            hanldeMessageFeedback={hanldeMessageFeedback}
          />
          <Separator
            orientation="vertical"
            className="data-[orientation=vertical]:h-4"
          />
          <CopyToClipboard
            variant="ghost"
            className="text-muted-foreground"
            text={parts.map((part) => part.data).join('')}
          />
        </div>
      </div>
    </div>
  );
};
