'use client';

import { Bot } from '@/api';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
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
} from '@/components/ui/dialog';
import { useTranslations } from 'next-intl';
import { useCallback, useRef, useState } from 'react';
import { toast } from 'sonner';

type ExportScope = 'bots' | 'prompts' | 'settings';

interface ImportValidation {
  bots_count: number;
  prompts_count: number;
  settings_count: number;
  has_secrets: boolean;
}

const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH || '';

async function fetchWithAuth(path: string, options: RequestInit) {
  const token = document.cookie
    .split('; ')
    .find((row) => row.startsWith('access_token='))
    ?.split('=')[1];

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(`${BASE_PATH}/api/v1${path}`, {
    ...options,
    headers,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || err.message || `HTTP ${res.status}`);
  }

  return res.json();
}

const ExportScopes: { key: ExportScope; labelKey: string }[] = [
  { key: 'bots', labelKey: 'scope.bots' },
  { key: 'prompts', labelKey: 'scope.prompts' },
  { key: 'settings', labelKey: 'scope.settings' },
];

export const BackupSettings = ({ bots = [] }: { bots?: Bot[] }) => {
  const admin_config = useTranslations('admin_config');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [exporting, setExporting] = useState(false);
  const [selectedScopes, setSelectedScopes] = useState<ExportScope[]>([
    'bots',
    'prompts',
    'settings',
  ]);
  const [includeSecrets, setIncludeSecrets] = useState(false);

  const [importDialogOpen, setImportDialogOpen] = useState(false);
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importing, setImporting] = useState(false);
  const [importValidation, setImportValidation] =
    useState<ImportValidation | null>(null);
  const [importStep, setImportStep] = useState<'validate' | 'confirm'>(
    'validate',
  );

  const handleScopeToggle = useCallback((scope: ExportScope) => {
    setSelectedScopes((prev) =>
      prev.includes(scope) ? prev.filter((s) => s !== scope) : [...prev, scope],
    );
  }, []);

  const t = (key: string) => admin_config(key as never);

  const handleExport = useCallback(async () => {
    if (selectedScopes.length === 0) {
      toast.error(t('backup.toast.no_scope'));
      return;
    }

    setExporting(true);
    try {
      const payload = {
        scope: selectedScopes,
        include_secrets: includeSecrets,
        bots:
          selectedScopes.includes('bots') && bots.length > 0
            ? bots.map((b) => b.id)
            : undefined,
      };

      const data = await fetchWithAuth('/backup/export', {
        method: 'POST',
        body: JSON.stringify(payload),
      });

      const json = JSON.stringify(data, null, 2);
      const blob = new Blob([json], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `sapilot-backup-${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success(t('backup.toast.export_success'));
    } catch {
      toast.error(t('backup.toast.export_failed'));
    } finally {
      setExporting(false);
    }
  }, [selectedScopes, includeSecrets, bots]);

  const handleImportFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file) return;
      if (!file.name.endsWith('.json')) {
        toast.error(t('backup.toast.invalid_file'));
        return;
      }
      setImportFile(file);
      setImportStep('validate');
      setImportValidation(null);
      setImportDialogOpen(true);
    },
    [],
  );

  const handleImportValidate = useCallback(async () => {
    if (!importFile) return;
    setImporting(true);
    try {
      const text = await importFile.text();
      const json = JSON.parse(text);

      const validation: ImportValidation = {
        bots_count: Array.isArray(json.bots) ? json.bots.length : 0,
        prompts_count: json.prompts ? Object.keys(json.prompts).length : 0,
        settings_count: json.settings ? Object.keys(json.settings).length : 0,
        has_secrets: !!json.has_secrets,
      };

      if (
        validation.bots_count === 0 &&
        validation.prompts_count === 0 &&
        validation.settings_count === 0
      ) {
        toast.error(t('backup.toast.empty_backup'));
        setImportDialogOpen(false);
        return;
      }

      setImportValidation(validation);
      setImportStep('confirm');
    } catch {
      toast.error(t('backup.toast.invalid_json'));
      setImportDialogOpen(false);
    } finally {
      setImporting(false);
    }
  }, [importFile]);

  const handleImportConfirm = useCallback(async () => {
    if (!importFile) return;
    setImporting(true);
    try {
      const text = await importFile.text();
      const json = JSON.parse(text);

      if (json.settings && Object.keys(json.settings).length > 0) {
        await fetchWithAuth('/backup/import/settings', {
          method: 'POST',
          body: JSON.stringify({ settings: json.settings }),
        });
      }

      if (json.prompts && Object.keys(json.prompts).length > 0) {
        await fetchWithAuth('/backup/import/prompts', {
          method: 'POST',
          body: JSON.stringify({ prompts: json.prompts }),
        });
      }

      if (json.bots && Array.isArray(json.bots) && json.bots.length > 0) {
        for (const bot of json.bots) {
          try {
            await fetchWithAuth('/bots', {
              method: 'POST',
              body: JSON.stringify(bot),
            });
          } catch {
            await fetchWithAuth(`/bots/${bot.id}`, {
              method: 'PUT',
              body: JSON.stringify(bot),
            });
          }
        }
      }

      toast.success(t('backup.toast.import_success'));
      setImportDialogOpen(false);
    } catch {
      toast.error(t('backup.toast.import_failed'));
    } finally {
      setImporting(false);
    }
  }, [importFile]);

  const triggerImportPicker = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  const totalSelected = importValidation
    ? importValidation.bots_count +
      importValidation.prompts_count +
      importValidation.settings_count
    : 0;

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t('backup.title')}</CardTitle>
        <CardDescription>{t('backup.description')}</CardDescription>
      </CardHeader>

      <CardContent className="flex flex-col gap-6">
        {/* Export Section */}
        <div className="flex flex-col gap-3">
          <h4 className="text-sm font-medium">{t('backup.export_section')}</h4>

          <div className="flex flex-wrap gap-2">
            {ExportScopes.map(({ key, labelKey }) => {
              const selected = selectedScopes.includes(key);
              return (
                <button
                  key={key}
                  type="button"
                  onClick={() => handleScopeToggle(key)}
                  className={`inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-sm transition-colors ${
                    selected
                      ? 'border-primary bg-primary/10 text-primary'
                      : 'border-border bg-background text-muted-foreground hover:border-primary/50'
                  }`}
                >
                  <Badge
                    variant={selected ? 'default' : 'secondary'}
                    className="h-5 w-5 rounded-full p-0 text-center text-xs"
                  >
                    {selected ? '✓' : ''}
                  </Badge>
                  <span>{t(`backup.${labelKey}`)}</span>
                </button>
              );
            })}
          </div>

          <div className="flex items-center gap-4">
            <label className="text-muted-foreground flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={includeSecrets}
                onChange={(e) => setIncludeSecrets(e.target.checked)}
                className="rounded border-gray-300"
              />
              {t('backup.include_secrets')}
            </label>

            <Button
              onClick={handleExport}
              disabled={exporting || selectedScopes.length === 0}
            >
              {exporting ? t('backup.exporting') : t('backup.action.export')}
            </Button>
          </div>
        </div>

        {/* Import Section */}
        <div className="flex flex-col gap-3">
          <h4 className="text-sm font-medium">{t('backup.import_section')}</h4>

          <div className="flex items-center gap-3">
            <input
              ref={fileInputRef}
              type="file"
              accept=".json"
              className="hidden"
              onChange={handleImportFileSelect}
            />
            <Button variant="outline" onClick={triggerImportPicker}>
              {t('backup.action.import')}
            </Button>
            <span className="text-muted-foreground text-xs">
              {t('backup.import_hint')}
            </span>
          </div>
        </div>
      </CardContent>

      {/* Import Validation Dialog */}
      <Dialog open={importDialogOpen} onOpenChange={setImportDialogOpen}>
        <DialogContent>
          {importStep === 'validate' && (
            <>
              <DialogHeader>
                <DialogTitle>{t('backup.import_validating')}</DialogTitle>
                <DialogDescription>
                  {t('backup.import_validating_desc')}
                </DialogDescription>
              </DialogHeader>
              <DialogFooter>
                <DialogClose asChild>
                  <Button variant="outline">{t('action.cancel')}</Button>
                </DialogClose>
                <Button onClick={handleImportValidate} disabled={importing}>
                  {importing
                    ? t('backup.validating')
                    : t('backup.action.validate')}
                </Button>
              </DialogFooter>
            </>
          )}

          {importStep === 'confirm' && importValidation && (
            <>
              <DialogHeader>
                <DialogTitle>{t('backup.import_confirm')}</DialogTitle>
                <DialogDescription>
                  {t('backup.import_confirm_desc')}
                </DialogDescription>
              </DialogHeader>

              <div className="bg-muted/50 flex flex-col gap-2 rounded-lg border p-4">
                {importValidation.bots_count > 0 && (
                  <div className="flex justify-between text-sm">
                    <span>{t('backup.scope.bots')}</span>
                    <span className="font-mono">
                      {importValidation.bots_count}
                    </span>
                  </div>
                )}
                {importValidation.prompts_count > 0 && (
                  <div className="flex justify-between text-sm">
                    <span>{t('backup.scope.prompts')}</span>
                    <span className="font-mono">
                      {importValidation.prompts_count}
                    </span>
                  </div>
                )}
                {importValidation.settings_count > 0 && (
                  <div className="flex justify-between text-sm">
                    <span>{t('backup.scope.settings')}</span>
                    <span className="font-mono">
                      {importValidation.settings_count}
                    </span>
                  </div>
                )}
                {importValidation.has_secrets && (
                  <div className="mt-2 text-xs text-amber-600">
                    {t('backup.has_secrets_warning')}
                  </div>
                )}
              </div>

              <DialogFooter>
                <DialogClose asChild>
                  <Button variant="outline">{t('action.cancel')}</Button>
                </DialogClose>
                <Button onClick={handleImportConfirm} disabled={importing}>
                  {importing
                    ? t('backup.importing')
                    : t('backup.action.confirm_import')}
                </Button>
              </DialogFooter>
            </>
          )}
        </DialogContent>
      </Dialog>
    </Card>
  );
};
