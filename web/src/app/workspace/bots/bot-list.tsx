'use client';

import { Bot } from '@/api';
import { FormatDate } from '@/components/format-date';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { apiClient } from '@/lib/api/client';
import {
  Calendar,
  Copy,
  MessageSquare,
  Pencil,
  Plus,
  Trash2,
} from 'lucide-react';
import { useTranslations } from 'next-intl';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useState } from 'react';
import { toast } from 'sonner';

export const BotList = ({ bots }: { bots: Bot[] }) => {
  const router = useRouter();
  const [searchValue, setSearchValue] = useState<string>('');
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [warningDialogOpen, setWarningDialogOpen] = useState(false);
  const [pendingDeleteBot, setPendingDeleteBot] = useState<Bot | null>(null);
  const page_bot = useTranslations('page_bot');
  const common_tips = useTranslations('common.tips');

  const handleDeleteClick = (bot: Bot) => {
    if (bot.is_default) {
      setWarningDialogOpen(true);
      return;
    }
    setPendingDeleteBot(bot);
    setDeleteDialogOpen(true);
  };

  const handleConfirmDelete = async () => {
    if (!pendingDeleteBot?.id) return;

    try {
      await apiClient.defaultApi.botsBotIdDelete({
        botId: pendingDeleteBot.id,
      });
      toast.success(common_tips('delete_success'));
      router.refresh();
    } catch {
      toast.error(common_tips('delete_failed'));
    }

    setDeleteDialogOpen(false);
    setPendingDeleteBot(null);
  };

  return (
    <>
      <div className="mb-4 flex flex-row items-center">
        <div>
          <Input
            placeholder={page_bot('search')}
            value={searchValue}
            onChange={(e) => setSearchValue(e.currentTarget.value)}
          />
        </div>
        <div className="ml-auto flex items-center gap-2">
          <Button asChild>
            <Link href="/workspace/bots/new">
              <Plus /> {page_bot('new_bot')}
            </Link>
          </Button>
        </div>
      </div>

      {bots.length === 0 ? (
        <div className="bg-accent/50 text-muted-foreground rounded-lg py-40 text-center">
          {page_bot('no_bots_found')}
        </div>
      ) : (
        <div className="sm:grid-col-1 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {bots
            .filter((bot) => {
              if (searchValue === '') return true;
              return (
                bot.title?.match(new RegExp(searchValue)) ||
                bot.description?.match(new RegExp(searchValue))
              );
            })
            .map((bot) => {
              return (
                <div key={bot.id} className="group relative">
                  <Card className="hover:bg-accent/30 gap-2 rounded-md">
                    <Link
                      href={`/workspace/bots/${bot.id}/chats`}
                      className="cursor-pointer"
                    >
                      <CardHeader className="px-4">
                        <div className="flex items-center justify-between">
                          <CardTitle className="h-5 truncate">
                            {bot.title}
                          </CardTitle>
                          {bot.is_default && (
                            <Badge variant="default" className="ml-2 shrink-0">
                              {page_bot('default_badge')}
                            </Badge>
                          )}
                        </div>
                      </CardHeader>
                      <CardDescription className="mb-4 truncate px-4">
                        {bot.description ||
                          page_bot('no_description_available')}
                      </CardDescription>
                    </Link>
                    <CardFooter className="flex items-center gap-2 px-4 pt-2 pb-3">
                      <div className="text-muted-foreground flex min-w-0 items-center gap-1 text-xs">
                        {bot.created && (
                          <div className="flex items-center gap-1">
                            <Calendar className="size-3" />
                            <FormatDate datetime={new Date(bot.created)} />
                          </div>
                        )}
                      </div>
                      <div className="ml-auto flex shrink-0 items-center gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-7 cursor-pointer px-2"
                          asChild
                          onClick={(e) => e.stopPropagation()}
                        >
                          <Link href={`/workspace/bots/${bot.id}/chats`}>
                            <MessageSquare className="mr-1 size-3" />
                            {page_bot('chats')}
                          </Link>
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-7 cursor-pointer px-2"
                          asChild
                          onClick={(e) => e.stopPropagation()}
                        >
                          <Link href={`/workspace/bots/${bot.id}/edit`}>
                            <Pencil className="mr-1 size-3" />
                            {page_bot('edit')}
                          </Link>
                        </Button>
                        {!bot.is_protected && (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-7 cursor-pointer px-2"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleDeleteClick(bot);
                            }}
                          >
                            <Trash2 className="mr-1 size-3" />
                            {page_bot('delete')}
                          </Button>
                        )}
                      </div>
                    </CardFooter>
                  </Card>

                  <div className="absolute top-2 right-2 z-10">
                    <Button
                      size="sm"
                      variant="secondary"
                      className="h-8 gap-1 opacity-0 transition-opacity group-hover:opacity-100"
                      asChild
                      onClick={(e) => e.stopPropagation()}
                    >
                      <Link href={`/workspace/bots/new?copyFrom=${bot.id}`}>
                        <Copy className="size-4" />
                        {page_bot('duplicate_bot')}
                      </Link>
                    </Button>
                  </div>
                </div>
              );
            })}
        </div>
      )}

      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {page_bot('delete_confirm_title')}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {page_bot('delete_confirm_message', {
                name: pendingDeleteBot?.title || '',
              })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{page_bot('cancel')}</AlertDialogCancel>
            <AlertDialogAction onClick={handleConfirmDelete}>
              {page_bot('confirm')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={warningDialogOpen} onOpenChange={setWarningDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {page_bot('delete_default_warning')}
            </AlertDialogTitle>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogAction onClick={() => setWarningDialogOpen(false)}>
              {page_bot('confirm')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
};
