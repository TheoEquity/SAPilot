'use client';

import type { LlmProviderModel } from '@/api';
import {
  FormControl,
  FormField,
  FormItem,
  FormLabel,
} from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { Textarea } from '@/components/ui/textarea';
import { useTranslations } from 'next-intl';
import type { UseFormReturn } from 'react-hook-form';
import type {
  SkillEditorFormInput,
  SkillEditorFormValues,
} from './skill-config';

type SkillEditorForm = UseFormReturn<
  SkillEditorFormInput,
  undefined,
  SkillEditorFormValues
>;

export const SkillBasicFields = ({ form }: { form: SkillEditorForm }) => {
  const page_bot = useTranslations('page_bot');
  return (
    <>
      <div className="grid gap-4 md:grid-cols-2">
        <FormField
          control={form.control}
          name="id"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{page_bot('skill_id')}</FormLabel>
              <FormControl>
                <Input {...field} value={field.value || ''} />
              </FormControl>
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="name"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{page_bot('title')}</FormLabel>
              <FormControl>
                <Input {...field} value={field.value || ''} />
              </FormControl>
            </FormItem>
          )}
        />
      </div>

      <FormField
        control={form.control}
        name="description"
        render={({ field }) => (
          <FormItem>
            <FormLabel>{page_bot('description')}</FormLabel>
            <FormControl>
              <Textarea {...field} value={field.value || ''} className="h-24" />
            </FormControl>
          </FormItem>
        )}
      />

      <div className="grid gap-4 md:grid-cols-2">
        <FormField
          control={form.control}
          name="type"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{page_bot('skill_type')}</FormLabel>
              <Select onValueChange={field.onChange} value={field.value}>
                <FormControl>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                </FormControl>
                <SelectContent>
                  <SelectItem value="workflow">
                    {page_bot('skill_type_workflow')}
                  </SelectItem>
                  <SelectItem value="hybrid">
                    {page_bot('skill_type_hybrid')}
                  </SelectItem>
                  <SelectItem value="llm">
                    {page_bot('skill_type_llm')}
                  </SelectItem>
                  <SelectItem value="tool">
                    {page_bot('skill_type_tool')}
                  </SelectItem>
                </SelectContent>
              </Select>
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="enabled"
          render={({ field }) => (
            <FormItem className="flex flex-row items-center justify-between rounded-lg border p-4">
              <FormLabel>{page_bot('skill_enabled')}</FormLabel>
              <FormControl>
                <Switch
                  checked={field.value}
                  onCheckedChange={field.onChange}
                />
              </FormControl>
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="is_fallback"
          render={({ field }) => (
            <FormItem className="flex flex-row items-center justify-between rounded-lg border p-4">
              <div>
                <FormLabel>{page_bot('skill_default')}</FormLabel>
                <p className="text-muted-foreground text-xs">
                  {page_bot('skill_default_desc')}
                </p>
              </div>
              <FormControl>
                <Switch
                  checked={field.value}
                  onCheckedChange={field.onChange}
                />
              </FormControl>
            </FormItem>
          )}
        />
      </div>
    </>
  );
};

export const SkillRuntimeFields = ({
  form,
  uniqueProviders,
  availableModels,
  setSelectedProvider,
}: {
  form: SkillEditorForm;
  uniqueProviders: string[];
  availableModels: LlmProviderModel[];
  setSelectedProvider: (provider: string) => void;
}) => {
  const page_bot = useTranslations('page_bot');
  return (
    <>
      <div className="grid gap-4 md:grid-cols-2">
        <FormField
          control={form.control}
          name="provider"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{page_bot('llm_provider')}</FormLabel>
              <Select
                onValueChange={(val) => {
                  field.onChange(val);
                  setSelectedProvider(val);
                }}
                value={field.value || ''}
                disabled={uniqueProviders.length === 0}
              >
                <FormControl>
                  <SelectTrigger>
                    <SelectValue placeholder={page_bot('select_provider')} />
                  </SelectTrigger>
                </FormControl>
                <SelectContent>
                  {uniqueProviders.map((p) => (
                    <SelectItem key={p} value={p}>
                      {p}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="model"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{page_bot('llm_model')}</FormLabel>
              <Select
                onValueChange={field.onChange}
                value={field.value || ''}
                disabled={availableModels.length === 0}
              >
                <FormControl>
                  <SelectTrigger>
                    <SelectValue placeholder={page_bot('select_model')} />
                  </SelectTrigger>
                </FormControl>
                <SelectContent>
                  {availableModels.map((m) => (
                    <SelectItem key={m.model} value={m.model}>
                      {m.model}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </FormItem>
          )}
        />
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <FormField
          control={form.control}
          name="temperature"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{page_bot('temperature')}</FormLabel>
              <FormControl>
                <Input
                  type="number"
                  step="0.1"
                  {...field}
                  value={
                    field.value === undefined || field.value === null
                      ? ''
                      : String(field.value)
                  }
                />
              </FormControl>
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="max_tokens"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{page_bot('max_tokens')}</FormLabel>
              <FormControl>
                <Input
                  type="number"
                  {...field}
                  value={
                    field.value === undefined || field.value === null
                      ? ''
                      : String(field.value)
                  }
                />
              </FormControl>
            </FormItem>
          )}
        />
      </div>
    </>
  );
};

export const SkillKnowledgeFields = ({
  form,
  collections,
}: {
  form: SkillEditorForm;
  collections: { id?: string; title?: string }[];
}) => {
  const page_bot = useTranslations('page_bot');
  return (
    <>
      <FormField
        control={form.control}
        name="collections"
        render={({ field }) => (
          <FormItem>
            <FormLabel>{page_bot('collection')}</FormLabel>
            <FormControl>
              <Select
                onValueChange={(val) => {
                  const current = field.value || [];
                  if (val === '__clear__') {
                    form.setValue('collections', []);
                  } else if (!current.some((c) => c.id === val)) {
                    form.setValue('collections', [...current, { id: val }]);
                  }
                }}
                value=""
              >
                <SelectTrigger className="w-full md:w-6/12">
                  <SelectValue
                    placeholder={page_bot('collection_placeholder')}
                  />
                </SelectTrigger>
                <SelectContent>
                  {collections.map((collection) => (
                    <SelectItem key={collection.id} value={collection.id || ''}>
                      {collection.title}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </FormControl>
            {field.value && field.value.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-2">
                {field.value.map((c) => {
                  const col = collections.find((col) => col.id === c.id);
                  return (
                    <span
                      key={c.id}
                      className="bg-secondary inline-flex items-center gap-1 rounded-md px-2 py-1 text-sm"
                    >
                      {col?.title || c.id}
                      <button
                        type="button"
                        className="hover:bg-accent ml-1 rounded-full"
                        onClick={() => {
                          form.setValue(
                            'collections',
                            field.value?.filter((item) => item.id !== c.id) ||
                              [],
                          );
                        }}
                      >
                        ×
                      </button>
                    </span>
                  );
                })}
              </div>
            )}
          </FormItem>
        )}
      />

      <FormField
        control={form.control}
        name="skill_prompt"
        render={({ field }) => (
          <FormItem>
            <FormLabel>{page_bot('skill_prompt_label')}</FormLabel>
            <FormControl>
              <Textarea
                {...field}
                value={field.value || ''}
                className="h-24 font-mono text-sm"
              />
            </FormControl>
          </FormItem>
        )}
      />
    </>
  );
};
