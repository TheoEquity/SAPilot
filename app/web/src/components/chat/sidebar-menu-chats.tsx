'use client';

import { useBotContext } from '@/components/providers/bot-provider';
import { Chat } from '@/api';
import { Button } from '@/components/ui/button';
import {
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuAction,
  SidebarMenuButton,
  SidebarMenuItem,
} from '@/components/ui/sidebar';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import _ from 'lodash';
import { Plus, Trash } from 'lucide-react';
import { useTranslations } from 'next-intl';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

export const SideBarMenuChats = () => {
  const { bot, workspace, chats, chatCreate, chatDelete } = useBotContext();
  const pathname = usePathname();
  const sidebar_workspace = useTranslations('sidebar_workspace');

  // 检查是否处于聊天界面
  // 匹配路径如 /workspace/bots/xxx/chats/xxx 或 /bots/xxx/chats/xxx
  const isInChatInterface = pathname.includes('/bots/') && pathname.includes('/chats');

  // 如果不在聊天界面，则不显示该组件
  if (!isInChatInterface) {
    return null;
  }

  const getChatTitle = (chat: Chat) => {
    const firstHumanMessage = chat.first_human_message?.trim();
    if (firstHumanMessage) {
      return _.truncate(firstHumanMessage, { length: 30 });
    }

    if (_.isEmpty(chat.title) || chat.title === 'New Chat') {
      return sidebar_workspace('display_empty_title');
    }

    return chat.title;
  };

  return (
    <SidebarGroup>
      <SidebarGroupLabel className="mb-1 flex flex-row justify-between pr-0">
        <span>{sidebar_workspace('chats')}</span>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              className="-mr-0.5 size-8 cursor-pointer"
              onClick={chatCreate}
              size="icon"
              variant="secondary"
            >
              <Plus />
              <span className="sr-only">{sidebar_workspace('chats_new')}</span>
            </Button>
          </TooltipTrigger>
          <TooltipContent side="right">
            {sidebar_workspace('chats_new')}
          </TooltipContent>
        </Tooltip>
      </SidebarGroupLabel>

      <SidebarGroupContent>
        <SidebarMenu>
          {chats?.map((chat) => {
            let url = `/bots/${bot?.id}/chats/${chat.id}`;
            if (workspace) {
              url = '/workspace' + url;
            }
            return (
              <SidebarMenuItem key={chat.id} className="group/item">
                <SidebarMenuButton
                  asChild
                  isActive={pathname === url}
                  className="data-[active=true]:font-normal"
                >
                  <Link href={url}>
                    <div className="truncate">{getChatTitle(chat)}</div>
                  </Link>
                </SidebarMenuButton>
                <SidebarMenuAction
                  className="invisible cursor-pointer group-hover/item:visible hover:bg-transparent"
                  onClick={() => chatDelete && chatDelete(chat)}
                >
                  <Trash className="text-muted-foreground" />
                </SidebarMenuAction>
              </SidebarMenuItem>
            );
          })}
        </SidebarMenu>
      </SidebarGroupContent>
    </SidebarGroup>
  );
};
