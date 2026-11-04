import { BotConfigProvider } from '@/components/providers/bot-config-provider';
import { getServerApi } from '@/lib/api/server';
import { notFound } from 'next/navigation';

export default async function BotSkillsLayout({
  params,
  children,
}: Readonly<{
  params: Promise<{ botId: string }>;
  children: React.ReactNode;
}>) {
  const { botId } = await params;
  const serverApi = await getServerApi();

  let bot;

  try {
    const botRes = await serverApi.defaultApi.botsBotIdGet({
      botId,
    });
    bot = botRes.data;
  } catch (err) {
    console.log(err);
  }

  if (!bot) {
    notFound();
  }

  return <BotConfigProvider bot={bot}>{children}</BotConfigProvider>;
}
