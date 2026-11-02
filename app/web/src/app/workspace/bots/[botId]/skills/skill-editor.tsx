'use client';

import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Form } from '@/components/ui/form';
import { useTranslations } from 'next-intl';
import Link from 'next/link';
import { FlowCanvasEditor } from '../flow-canvas-editor';
import { FlowJsonEditor } from '../flow-json-editor';
import {
  SkillBasicFields,
  SkillKnowledgeFields,
  SkillRuntimeFields,
} from './skill-editor-fields';
import { useSkillEditor } from './use-skill-editor';

export const SkillEditor = ({ skillId }: { skillId?: string }) => {
  const page_bot = useTranslations('page_bot');
  const {
    bot,
    existingSkill,
    form,
    flowDraft,
    setFlowDraft,
    collections,
    uniqueProviders,
    availableModels,
    setSelectedProvider,
    handleSave,
    handleQuickSave,
    skillOptions,
    skillTools,
  } = useSkillEditor(skillId);

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          {existingSkill ? existingSkill.name : page_bot('new_skill')}
        </CardTitle>
        <CardDescription>{page_bot('skills_description')}</CardDescription>
      </CardHeader>
      <CardContent>
        <Form {...form}>
          <form onSubmit={handleSave} className="flex flex-col gap-6">
            <SkillBasicFields form={form} />
            <SkillRuntimeFields
              form={form}
              uniqueProviders={uniqueProviders}
              availableModels={availableModels}
              setSelectedProvider={setSelectedProvider}
            />
            <SkillKnowledgeFields form={form} collections={collections} />

            <FlowCanvasEditor
              title={page_bot('skill_flow_canvas_title')}
              description={page_bot('skill_flow_canvas_description')}
              value={flowDraft}
              onChange={setFlowDraft}
              onQuickSave={handleQuickSave}
              skillOptions={skillOptions}
              skillTools={skillTools}
            />

            <details className="group rounded-md border [&>summary]:flex [&>summary]:cursor-pointer [&>summary]:list-none [&>summary]:items-center [&>summary]:gap-2 [&>summary]:p-3 [&>summary::-webkit-details-marker]:hidden [&[open]>summary]:border-b">
              <summary className="font-medium select-none">
                {page_bot('skill_flow_title')}
                <span className="transition-transform group-open:rotate-90">
                  ▶
                </span>
              </summary>
              <div className="p-4">
                <FlowJsonEditor
                  title={page_bot('skill_flow_title')}
                  description={page_bot('skill_flow_description')}
                  value={flowDraft}
                  onChange={setFlowDraft}
                />
              </div>
            </details>

            <div className="flex gap-3">
              <Button variant="outline" asChild>
                <Link href={`/workspace/bots/${bot.id}/skills`}>
                  {page_bot('cancel')}
                </Link>
              </Button>
              <Button type="submit">{page_bot('save_settings')}</Button>
            </div>
          </form>
        </Form>
      </CardContent>
    </Card>
  );
};
