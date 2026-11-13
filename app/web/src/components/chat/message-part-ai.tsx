import { Markdown } from '@/components/markdown';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import _ from 'lodash';
import { AlertCircleIcon } from 'lucide-react';
import { useCallback, useState } from 'react';
import type { ChatMessage } from './chat-message';
import { MessageCollapseContent } from './message-collapse-content';

const isFaqOption = (
  value: unknown,
): value is { action: string; label: string } =>
  typeof value === 'object' &&
  value !== null &&
  'action' in value &&
  typeof value.action === 'string' &&
  'label' in value &&
  typeof value.label === 'string';

export const MessagePartAi = ({
  part,
  loading,
  onFaqChoice,
}: {
  part: ChatMessage;
  loading: boolean;
  onFaqChoice: (action: string, label: string, turnId: string) => void;
}) => {
  const [faqChoiceSubmitted, setFaqChoiceSubmitted] = useState(false);
  const parseToolCall = useCallback(
    (content: string): { title: string; body: string } => {
      const lines = content.split('\n');
      const firstLine = lines[0] || '';
      const titleMatch = firstLine.match(/^\*\*(.*?)\*\*$/);
      if (titleMatch) {
        const title = _.truncate(titleMatch[1].trim(), { length: 100 });
        const body = lines.slice(1).join('\n').trim();
        return { title, body };
      }
      return { title: 'Tool call', body: content };
    },
    [],
  );
  switch (part.type) {
    case 'error':
      return (
        <Alert variant="destructive">
          <AlertCircleIcon />
          <AlertDescription>{part.data}</AlertDescription>
        </Alert>
      );
    case 'thinking':
      return (
        <MessageCollapseContent title="Thinging" animate={loading}>
          <Markdown>{part.data ?? undefined}</Markdown>
        </MessageCollapseContent>
      );
    case 'tool_call_result':
      const { title, body } = parseToolCall(part.data || '');
      return (
        <MessageCollapseContent title={title} animate={loading}>
          <Markdown>{body}</Markdown>
        </MessageCollapseContent>
      );
    case 'message':
      return <Markdown>{part.data ?? undefined}</Markdown>;
    case 'faq_choice': {
      const options = part.options?.filter(isFaqOption) || [
        { action: 'faq_expand', label: '是，专业扩展' },
        { action: 'faq_end', label: '否，结束' },
      ];
      return (
        <div className="mt-3 flex flex-col gap-2 rounded-md border p-3 sm:flex-row sm:items-center">
          <span className="text-muted-foreground text-sm">
            {part.data || '是否需要我从专业角度扩展解答？'}
          </span>
          <div className="flex flex-row gap-2">
            {options.map((option) => (
              <Button
                key={option.action}
                size="sm"
                variant={option.action === 'faq_expand' ? 'default' : 'outline'}
                disabled={faqChoiceSubmitted || !part.id}
                onClick={() => {
                  if (part.id) {
                    setFaqChoiceSubmitted(true);
                    onFaqChoice(option.action, option.label, part.id);
                  }
                }}
              >
                {option.label}
              </Button>
            ))}
          </div>
        </div>
      );
    }
    case 'stop':
      return '';
    default:
      return part.data;
  }
};
