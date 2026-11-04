'use client';

import { FormatDate } from '@/components/format-date';
import { PageContent } from '@/components/page-container';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardAction,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Separator } from '@/components/ui/separator';
import { useBotConfigContext } from '@/components/providers/bot-config-provider';
import { cn } from '@/lib/utils';
import { Calendar, EllipsisVertical, MessageSquare, Settings, Trash } from 'lucide-react';
import { useTranslations } from 'next-intl';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import _ from 'lodash';

export const BotHeader = ({ className }: { className?: string }) => {
  const { bot } = useBotConfigContext();
  const pathname = usePathname();
  const page_bot = useTranslations('page_bot');

  const urls = {
    chats: `/workspace/bots/${bot.id}/chats`,
    settings: `/workspace/bots/${bot.id}/settings`,
  };

  return (
    <PageContent className={cn('flex flex-col gap-4 pb-0', className)}>
      <Card className="gap-0 p-0">
        <CardHeader className="p-4">
          <CardTitle className="text-2xl">{bot.title}</CardTitle>
          <CardDescription className="flex flex-row items-center gap-6">
            <div>
              {bot.created && (
                <div className="text-muted-foreground flex items-center gap-1 text-sm">
                  <Calendar className="size-3" />
                  <FormatDate datetime={new Date(bot.created)} />
                </div>
              )}
            </div>
            <div className="flex items-center gap-2">
              <Badge variant="outline">
                {_.upperFirst(_.lowerCase(bot.type || 'agent'))}
              </Badge>
            </div>
          </CardDescription>
          <CardAction className="flex flex-row items-center gap-4">
            {bot.is_protected && (
              <Badge variant="secondary">
                {page_bot('protected')}
              </Badge>
            )}

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button size="icon" variant="ghost">
                  <EllipsisVertical />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-60">
                <DropdownMenuItem asChild>
                  <Link href={urls.chats}>
                    <MessageSquare /> {page_bot('view_chats')}
                  </Link>
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                {!bot.is_protected && (
                  <DropdownMenuItem variant="destructive" asChild>
                    <Link href={`/workspace/bots/${bot.id}/delete`}>
                      <Trash /> {page_bot('delete_bot')}
                    </Link>
                  </DropdownMenuItem>
                )}
              </DropdownMenuContent>
            </DropdownMenu>
          </CardAction>
        </CardHeader>
        <CardDescription className="mb-4 px-4">
          {_.truncate(
            bot.description || page_bot('no_description_available'),
            {
              length: 180,
            },
          )}
        </CardDescription>
        <Separator />
        <div className="bg-accent/50 flex flex-row gap-2 rounded-b-xl px-4">
          <Button
            asChild
            data-active={Boolean(pathname.match(urls.chats))}
            className="hover:border-b-primary data-[active=true]:border-b-primary h-10 rounded-none border-y-2 border-y-transparent px-1 has-[>svg]:px-2"
            variant="ghost"
          >
            <Link href={urls.chats}>
              <MessageSquare />
              <span className="hidden sm:inline">
                {page_bot('chats')}
              </span>
            </Link>
          </Button>

          <Button
            asChild
            data-active={Boolean(pathname.match(urls.settings))}
            className="hover:border-b-primary data-[active=true]:border-b-primary h-10 rounded-none border-y-2 border-y-transparent px-1 has-[>svg]:px-2"
            variant="ghost"
          >
            <Link href={urls.settings}>
              <Settings />{' '}
              <span className="hidden sm:inline">
                {page_bot('bot_settings')}
              </span>
            </Link>
          </Button>
        </div>
      </Card>
    </PageContent>
  );
};
