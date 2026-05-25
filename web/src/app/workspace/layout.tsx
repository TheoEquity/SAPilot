import { AppLogo } from '@/components/app-topbar';
import {
  Sidebar,
  SidebarContent,
  SidebarHeader,
  SidebarInset,
  SidebarProvider,
} from '@/components/ui/sidebar';
import { getServerApi } from '@/lib/api/server';
import { redirect } from 'next/navigation';

import { SideBarMenuChats } from '@/components/chat/sidebar-menu-chats';
import { BotProvider } from '@/components/providers/bot-provider';
import { MenuFooter } from './menu-footer';
import { MenuMain } from './menu-main';

export default async function Layout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  let user;
  const apiServer = await getServerApi();

  try {
    const res = await apiServer.defaultApi.userGet();
    user = res.data;
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
  } catch (err) {}

  if (!user) {
    redirect(`/auth/signin?callbackUrl=${encodeURIComponent('/workspace/bots')}`);
  }

  return (
    <BotProvider workspace={true} chats={[]}>
      <SidebarProvider>
        <Sidebar>
          <SidebarHeader className="h-16 flex-row items-center gap-4 px-4 align-middle">
            <AppLogo />
          </SidebarHeader>
          <SidebarContent className="gap-0">
            <MenuMain />
            <SideBarMenuChats />
          </SidebarContent>

          <MenuFooter />
        </Sidebar>
        <SidebarInset>{children}</SidebarInset>
      </SidebarProvider>
    </BotProvider>
  );
}
