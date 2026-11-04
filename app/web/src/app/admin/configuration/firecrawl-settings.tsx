'use client';

import { Settings } from '@/api';
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
import { apiClient } from '@/lib/api/client';
import { useTranslations } from 'next-intl';
import { useCallback, useEffect, useState } from 'react';
import { toast } from 'sonner';

const defaultValue: Settings = {
  firecrawl_api_key: '',
  firecrawl_api_url: 'https://api.firecrawl.dev/v1',
};

export const FirecrawlSettings = ({ data: initData }: { data: Settings }) => {
  const [data, setData] = useState<Settings>({
    ...defaultValue,
    ...initData,
  });
  const [saving, setSaving] = useState(false);
  const admin_config = useTranslations('admin_config');
  const common_action = useTranslations('common.action');
  const common_tips = useTranslations('common.tips');

  const updateField = useCallback(
    <K extends keyof Settings>(key: K, value: Settings[K]) => {
      setData((current) => ({ ...current, [key]: value }));
    },
    [],
  );

  const handleSave = useCallback(async () => {
    setSaving(true);
    try {
      await apiClient.defaultApi.settingsPut({ settings: data });
      toast.success(common_tips('save_success'));
    } finally {
      setSaving(false);
    }
  }, [common_tips, data]);

  useEffect(() => {
    setData({
      ...defaultValue,
      ...initData,
    });
  }, [initData]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>{admin_config('firecrawl_title')}</CardTitle>
        <CardDescription>
          {admin_config('firecrawl_description')}
        </CardDescription>
      </CardHeader>

      <CardContent className="grid gap-4 md:grid-cols-2">
        <div className="flex flex-col gap-2 md:col-span-2">
          <Label>{admin_config('firecrawl_api_key')}</Label>
          <Input
            type="password"
            value={data.firecrawl_api_key || ''}
            onChange={(e) => updateField('firecrawl_api_key', e.target.value)}
          />
        </div>

        <div className="flex flex-col gap-2 md:col-span-2">
          <Label>{admin_config('firecrawl_api_url')}</Label>
          <Input
            value={
              data.firecrawl_api_url || defaultValue.firecrawl_api_url || ''
            }
            onChange={(e) => updateField('firecrawl_api_url', e.target.value)}
          />
        </div>
      </CardContent>

      <CardFooter className="justify-end">
        <Button disabled={saving} onClick={handleSave}>
          {common_action('save')}
        </Button>
      </CardFooter>
    </Card>
  );
};
