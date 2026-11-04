'use client';

import { PromptDetail, UserPromptsResponse } from '@/api';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Textarea } from '@/components/ui/textarea';
import { apiClient } from '@/lib/api/client';
import { useTranslations } from 'next-intl';
import { useRouter } from 'next/navigation';
import { useCallback, useEffect, useState } from 'react';
import { toast } from 'sonner';

type PromptType =
  | 'agent_system'
  | 'agent_query'
  | 'index_graph'
  | 'index_summary'
  | 'index_vision';

const PROMPT_TYPES: PromptType[] = [
  'agent_system',
  'agent_query',
  'index_graph',
  'index_summary',
  'index_vision',
];

interface PromptCardProps {
  promptType: PromptType;
  detail: PromptDetail | undefined;
  onSaved: () => void;
}

const PromptCard = ({ promptType, detail, onSaved }: PromptCardProps) => {
  const page_prompts = useTranslations('page_prompts');
  const common_action = useTranslations('common.action');
  const [content, setContent] = useState(detail?.content ?? '');
  const [saving, setSaving] = useState(false);
  const [resetOpen, setResetOpen] = useState(false);

  useEffect(() => {
    setContent(detail?.content ?? '');
  }, [detail?.content]);

  const handleSave = useCallback(async () => {
    setSaving(true);
    try {
      await apiClient.defaultApi.promptsUserPut({
        updateUserPromptsRequest: {
          prompts: { [promptType]: content },
        },
      });
      toast.success(page_prompts('toast.save_success'));
      onSaved();
    } finally {
      setSaving(false);
    }
  }, [content, promptType, page_prompts, onSaved]);

  const handleReset = useCallback(async () => {
    await apiClient.defaultApi.promptsUserPromptTypeDelete({
      promptType: promptType as never,
    });
    toast.success(page_prompts('toast.reset_success'));
    setResetOpen(false);
    onSaved();
  }, [promptType, page_prompts, onSaved]);

  const isCustomized = detail?.customized === true;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between gap-2">
          <CardTitle>{page_prompts(`${promptType}.title` as never)}</CardTitle>
          <Badge variant={isCustomized ? 'default' : 'secondary'}>
            {isCustomized
              ? page_prompts('status.customized')
              : page_prompts('status.default')}
          </Badge>
        </div>
        <CardDescription>
          {page_prompts(`${promptType}.description` as never)}
        </CardDescription>
      </CardHeader>

      <CardContent>
        <Textarea
          className="max-h-[360px] min-h-[160px] resize-y font-mono text-sm"
          value={content}
          onChange={(e) => setContent(e.target.value)}
          placeholder={detail?.content ?? ''}
        />
      </CardContent>

      <CardFooter className="justify-end gap-2">
        {isCustomized && (
          <Dialog open={resetOpen} onOpenChange={setResetOpen}>
            <DialogTrigger asChild>
              <Button variant="outline">{page_prompts('action.reset')}</Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>
                  {page_prompts('action.reset_confirm')}
                </DialogTitle>
                <DialogDescription>
                  {page_prompts('action.reset_confirm_description')}
                </DialogDescription>
              </DialogHeader>
              <DialogFooter>
                <DialogClose asChild>
                  <Button variant="outline">{common_action('cancel')}</Button>
                </DialogClose>
                <Button variant="destructive" onClick={handleReset}>
                  {page_prompts('action.reset')}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        )}
        <Button onClick={handleSave} disabled={saving}>
          {page_prompts('action.save')}
        </Button>
      </CardFooter>
    </Card>
  );
};

export const PromptSettings = ({ data }: { data: UserPromptsResponse }) => {
  const router = useRouter();
  const page_prompts = useTranslations('page_prompts');
  const [resetAllOpen, setResetAllOpen] = useState(false);
  const [resettingAll, setResettingAll] = useState(false);

  const handleSaved = useCallback(() => {
    setTimeout(router.refresh, 300);
  }, [router]);

  const handleResetAll = useCallback(async () => {
    setResettingAll(true);
    try {
      await apiClient.defaultApi.promptsUserResetPost({
        resetPromptsRequest: {},
      });
      toast.success(page_prompts('toast.reset_all_success' as never));
      setResetAllOpen(false);
      handleSaved();
    } finally {
      setResettingAll(false);
    }
  }, [page_prompts, handleSaved]);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-muted-foreground text-sm font-medium">
            {page_prompts('section.types' as never)}
          </h3>
        </div>
        <Dialog open={resetAllOpen} onOpenChange={setResetAllOpen}>
          <DialogTrigger asChild>
            <Button variant="outline" size="sm">
              {page_prompts('action.reset_all' as never)}
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>
                {page_prompts('action.reset_all_confirm' as never)}
              </DialogTitle>
              <DialogDescription>
                {page_prompts('action.reset_all_confirm_description' as never)}
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <DialogClose asChild>
                <Button variant="outline">
                  {page_prompts('action.cancel' as never)}
                </Button>
              </DialogClose>
              <Button
                variant="destructive"
                onClick={handleResetAll}
                disabled={resettingAll}
              >
                {page_prompts('action.reset_all' as never)}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {PROMPT_TYPES.map((promptType) => (
        <PromptCard
          key={promptType}
          promptType={promptType}
          detail={data[promptType]}
          onSaved={handleSaved}
        />
      ))}
    </div>
  );
};
