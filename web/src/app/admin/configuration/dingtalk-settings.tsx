'use client';

import { Bot, Settings } from '@/api';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { apiClient } from '@/lib/api/client';
import Link from 'next/link';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { toast } from 'sonner';

const defaultValue: Settings = {
  dingtalk_enabled: false,
  dingtalk_webhook_secret: '',
  dingtalk_outgoing_webhook_url: '',
  dingtalk_outgoing_webhook_secret: '',
  dingtalk_bot_id: '',
  dingtalk_response_mode: 'sync',
  dingtalk_robot_code: '',
  dingtalk_app_key: '',
  dingtalk_app_secret: '',
};

export const DingTalkSettings = ({
  data: initData,
  bots: initBots,
}: {
  data: Settings;
  bots: Bot[];
}) => {
  const [data, setData] = useState<Settings>({
    ...defaultValue,
    ...initData,
  });
  const [saving, setSaving] = useState(false);

  const agentBots = useMemo(
    () => initBots.filter((bot) => bot.type === 'agent'),
    [initBots],
  );

  const updateField = useCallback(
    <K extends keyof Settings>(key: K, value: Settings[K]) => {
      setData((current) => ({ ...current, [key]: value }));
    },
    [],
  );

  const handleSave = useCallback(async () => {
    if (data.dingtalk_enabled && !data.dingtalk_bot_id) {
      toast.error('启用钉钉接口前，请先绑定一个 Agent');
      return;
    }

    setSaving(true);
    try {
      await apiClient.defaultApi.settingsPut({ settings: data });
      toast.success('钉钉接口配置已保存');
    } finally {
      setSaving(false);
    }
  }, [data]);

  useEffect(() => {
    setData({
      ...defaultValue,
      ...initData,
    });
  }, [initData]);

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between gap-4">
          <div>
            <CardTitle>钉钉接口配置</CardTitle>
            <CardDescription>
              绑定管理员创建的钉钉现场问诊 Agent，并配置钉钉 App 与机器人参数。
            </CardDescription>
          </div>
          <Switch
            checked={Boolean(data.dingtalk_enabled)}
            onCheckedChange={(checked) =>
              updateField('dingtalk_enabled', checked)
            }
          />
        </div>
      </CardHeader>

      <CardContent className="grid gap-4 md:grid-cols-2">
        <div className="flex flex-col gap-2">
          <Label>绑定 SAPilot Agent</Label>
          <Select
            value={data.dingtalk_bot_id || ''}
            onValueChange={(value) => updateField('dingtalk_bot_id', value)}
          >
            <SelectTrigger>
              <SelectValue placeholder="选择钉钉现场问诊 Agent" />
            </SelectTrigger>
            <SelectContent>
              {agentBots.map((bot) => (
                <SelectItem key={bot.id} value={bot.id || ''}>
                  {bot.title || bot.id}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <div className="text-muted-foreground text-sm">
            启用后该 Agent 会进入删除保护。需要新建时请先到 Agent 页面创建。
          </div>
        </div>

        <div className="flex flex-col gap-2">
          <Label>回复模式</Label>
          <Select
            value={data.dingtalk_response_mode || 'sync'}
            onValueChange={(value) =>
              updateField('dingtalk_response_mode', value)
            }
          >
            <SelectTrigger>
              <SelectValue placeholder="选择回复模式" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="sync">同步响应</SelectItem>
              <SelectItem value="webhook">Webhook 异步响应</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="flex flex-col gap-2">
          <Label>钉钉 AppKey</Label>
          <Input
            value={data.dingtalk_app_key || ''}
            onChange={(e) => updateField('dingtalk_app_key', e.target.value)}
          />
        </div>

        <div className="flex flex-col gap-2">
          <Label>钉钉 AppSecret</Label>
          <Input
            type="password"
            value={data.dingtalk_app_secret || ''}
            onChange={(e) => updateField('dingtalk_app_secret', e.target.value)}
          />
        </div>

        <div className="flex flex-col gap-2">
          <Label>回调验签 Secret</Label>
          <Input
            type="password"
            value={data.dingtalk_webhook_secret || ''}
            onChange={(e) =>
              updateField('dingtalk_webhook_secret', e.target.value)
            }
          />
        </div>

        <div className="flex flex-col gap-2">
          <Label>RobotCode</Label>
          <Input
            value={data.dingtalk_robot_code || ''}
            onChange={(e) => updateField('dingtalk_robot_code', e.target.value)}
          />
        </div>

        <div className="flex flex-col gap-2 md:col-span-2">
          <Label>Outgoing Webhook URL</Label>
          <Input
            value={data.dingtalk_outgoing_webhook_url || ''}
            onChange={(e) =>
              updateField('dingtalk_outgoing_webhook_url', e.target.value)
            }
          />
        </div>

        <div className="flex flex-col gap-2 md:col-span-2">
          <Label>Outgoing Webhook Secret</Label>
          <Input
            type="password"
            value={data.dingtalk_outgoing_webhook_secret || ''}
            onChange={(e) =>
              updateField('dingtalk_outgoing_webhook_secret', e.target.value)
            }
          />
        </div>
      </CardContent>

      <CardFooter className="justify-between gap-4">
        <Button variant="outline" asChild>
          <Link href="/workspace/bots/new">新建 Agent</Link>
        </Button>
        <Button disabled={saving} onClick={handleSave}>
          保存钉钉配置
        </Button>
      </CardFooter>
    </Card>
  );
};
