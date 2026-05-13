'use client';

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
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Download, Upload } from 'lucide-react';
import { useCallback, useState } from 'react';
import { toast } from 'sonner';

async function apiGet<T>(url: string): Promise<T> {
  const res = await fetch(url, { credentials: 'include' });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function apiPost<T>(url: string, body: unknown, params?: Record<string, string>): Promise<T> {
  const qs = params ? '?' + new URLSearchParams(params).toString() : '';
  const res = await fetch(`${url}${qs}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    credentials: 'include',
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export const ConfigExportImport = () => {
  const [exporting, setExporting] = useState(false);
  const [importing, setImporting] = useState(false);
  const [importDialogOpen, setImportDialogOpen] = useState(false);
  const [importMode, setImportMode] = useState<'merge' | 'replace'>('merge');
  const [pendingFile, setPendingFile] = useState<File | null>(null);

  const handleExport = useCallback(async () => {
    setExporting(true);
    try {
      const data = await apiGet('/api/v1/settings/export');
      const blob = new Blob([JSON.stringify(data, null, 2)], {
        type: 'application/json',
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `sapilot-config-export-${new Date().toISOString().slice(0, 10)}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      toast.success('配置导出成功');
    } catch {
      toast.error('配置导出失败');
    } finally {
      setExporting(false);
    }
  }, []);

  const handleFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) {
        setPendingFile(file);
        setImportDialogOpen(true);
      }
      e.target.value = '';
    },
    [],
  );

  const handleImport = useCallback(async () => {
    if (!pendingFile) return;
    setImporting(true);
    setImportDialogOpen(false);
    try {
      const text = await pendingFile.text();
      const data = JSON.parse(text);
      const result = await apiPost('/api/v1/settings/import', data, {
        mode: importMode,
      });
      const messages: string[] = [];
      if (result.bots_created > 0) messages.push(`创建 ${result.bots_created} 个 Agent`);
      if (result.bots_skipped > 0) messages.push(`跳过 ${result.bots_skipped} 个已存在的 Agent`);
      if (result.errors?.length) {
        messages.push(`${result.errors.length} 个错误`);
      }
      toast.success(messages.length ? messages.join('，') : '导入完成');
    } catch {
      toast.error('配置导入失败，请检查文件格式');
    } finally {
      setImporting(false);
      setPendingFile(null);
    }
  }, [pendingFile, importMode]);

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle>配置导入 / 导出</CardTitle>
          <CardDescription>
            导出当前所有 Agent 配置（含提示词、模型设置、知识库绑定）和钉钉设置，用于备份或迁移。
          </CardDescription>
        </CardHeader>

        <CardContent className="flex flex-col gap-4 sm:flex-row">
          <Button onClick={handleExport} disabled={exporting} className="flex items-center gap-2">
            <Download className="size-4" />
            {exporting ? '导出中...' : '导出配置'}
          </Button>

          <label className="flex items-center">
            <Button
              asChild
              disabled={importing}
              className="flex items-center gap-2"
            >
              <span>
                <Upload className="size-4" />
                {importing ? '导入中...' : '导入配置'}
              </span>
            </Button>
            <input
              type="file"
              accept=".json"
              className="hidden"
              onChange={handleFileSelect}
            />
          </label>
        </CardContent>

        <CardFooter className="text-muted-foreground text-sm">
          提示：导出文件包含所有 Agent 的提示词和配置，不含知识库文档内容。
        </CardFooter>
      </Card>

      <AlertDialog open={importDialogOpen} onOpenChange={setImportDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>确认导入模式</AlertDialogTitle>
            <AlertDialogDescription>
              选择导入方式：合并模式会跳过已存在的 Agent（按名称匹配），
              替换模式会先删除现有所有 Agent 再导入。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <div className="flex gap-2">
            <Button
              variant={importMode === 'merge' ? 'default' : 'outline'}
              onClick={() => setImportMode('merge')}
            >
              合并（跳过已存在）
            </Button>
            <Button
              variant={importMode === 'replace' ? 'default' : 'outline'}
              onClick={() => setImportMode('replace')}
            >
              替换（先删后建）
            </Button>
          </div>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => setPendingFile(null)}>取消</AlertDialogCancel>
            <AlertDialogAction onClick={handleImport}>确认导入</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
};
