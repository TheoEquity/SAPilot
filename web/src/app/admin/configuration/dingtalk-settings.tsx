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
import { useTranslations } from 'next-intl';
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
  const admin_config = useTranslations('admin_config');
  const common_action = useTranslations('common.action');
  const common_tips = useTranslations('common.tips');

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
      toast.error(admin_config('dingtalk_bind_agent_required'));
      return;
    }

    setSaving(true);
    try {
      await apiClient.defaultApi.settingsPut({ settings: data });
      toast.success(common_tips('save_success'));
    } finally {
      setSaving(false);
    }
  }, [admin_config, common_tips, data]);

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
            <CardTitle>{admin_config('dingtalk_title')}</CardTitle>
            <CardDescription>
              {admin_config('dingtalk_description')}
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
          <Label>{admin_config('dingtalk_agent_label')}</Label>
          <Select
            value={data.dingtalk_bot_id || ''}
            onValueChange={(value) => updateField('dingtalk_bot_id', value)}
          >
            <SelectTrigger>
              <SelectValue
                placeholder={admin_config('dingtalk_agent_placeholder')}
              />
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
            {admin_config('dingtalk_agent_hint')}
          </div>
        </div>

        <div className="flex flex-col gap-2">
          <Label>{admin_config('dingtalk_response_mode')}</Label>
          <Select
            value={data.dingtalk_response_mode || 'sync'}
            onValueChange={(value) =>
              updateField('dingtalk_response_mode', value)
            }
          >
            <SelectTrigger>
              <SelectValue
                placeholder={admin_config('dingtalk_response_mode_placeholder')}
              />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="sync">
                {admin_config('dingtalk_response_mode_sync')}
              </SelectItem>
              <SelectItem value="webhook">
                {admin_config('dingtalk_response_mode_webhook')}
              </SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="flex flex-col gap-2">
          <Label>{admin_config('dingtalk_app_key')}</Label>
          <Input
            value={data.dingtalk_app_key || ''}
            onChange={(e) => updateField('dingtalk_app_key', e.target.value)}
          />
        </div>

        <div className="flex flex-col gap-2">
          <Label>{admin_config('dingtalk_app_secret')}</Label>
          <Input
            type="password"
            value={data.dingtalk_app_secret || ''}
            onChange={(e) => updateField('dingtalk_app_secret', e.target.value)}
          />
        </div>

        <div className="flex flex-col gap-2">
          <Label>{admin_config('dingtalk_webhook_secret')}</Label>
          <Input
            type="password"
            value={data.dingtalk_webhook_secret || ''}
            onChange={(e) =>
              updateField('dingtalk_webhook_secret', e.target.value)
            }
          />
        </div>

        <div className="flex flex-col gap-2">
          <Label>{admin_config('dingtalk_robot_code')}</Label>
          <Input
            value={data.dingtalk_robot_code || ''}
            onChange={(e) => updateField('dingtalk_robot_code', e.target.value)}
          />
        </div>

        <div className="flex flex-col gap-2 md:col-span-2">
          <Label>{admin_config('dingtalk_outgoing_webhook_url')}</Label>
          <Input
            value={data.dingtalk_outgoing_webhook_url || ''}
            onChange={(e) =>
              updateField('dingtalk_outgoing_webhook_url', e.target.value)
            }
          />
        </div>

        <div className="flex flex-col gap-2 md:col-span-2">
          <Label>{admin_config('dingtalk_outgoing_webhook_secret')}</Label>
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
          <Link href="/workspace/bots/new">
            {admin_config('dingtalk_create_agent')}
          </Link>
        </Button>
        <Button disabled={saving} onClick={handleSave}>
          {common_action('save')}
        </Button>
      </CardFooter>
    </Card>
  );
};
