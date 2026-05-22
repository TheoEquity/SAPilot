'use client';

import { useBotConfigContext } from '@/components/providers/bot-config-provider';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import Link from 'next/link';
import { useTranslations } from 'next-intl';
import { toast } from 'sonner';
import { normalizeOrchestration, updateBotOrchestration } from '../bot-config-updater';

export const SkillList = () => {
  const { bot, loadBot } = useBotConfigContext();
  const page_bot = useTranslations('page_bot');
  const common_tips = useTranslations('common.tips');

  const orchestration = normalizeOrchestration(bot);
  const skills = orchestration.skills || [];

  const handleDelete = async (skillId: string) => {
    const nextSkills = skills.filter((skill) => skill.id !== skillId);
    const nextFallbackSkillId =
      orchestration.intent_router?.fallback_skill_id === skillId
        ? nextSkills[0]?.id || ''
        : orchestration.intent_router?.fallback_skill_id;

    const nextOrchestration = {
      ...orchestration,
      skills: nextSkills,
      intent_router: orchestration.intent_router
        ? {
            ...orchestration.intent_router,
            fallback_skill_id: nextFallbackSkillId,
            candidate_skills:
              orchestration.intent_router.candidate_skills?.filter(
                (candidate) => candidate.skill_id !== skillId,
              ) || [],
          }
        : orchestration.intent_router,
    };

    await updateBotOrchestration({
      bot,
      orchestration: nextOrchestration,
    });

    await loadBot();
    toast.success(common_tips('delete_success'));
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>{page_bot('skills_title')}</CardTitle>
        <CardDescription>{page_bot('skills_description')}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {skills.length === 0 ? (
          <p className="text-muted-foreground text-sm">
            {page_bot('orchestration_not_configured')}
          </p>
        ) : (
          skills.map((skill) => (
            <div
              key={skill.id}
              className="flex flex-col gap-3 rounded-lg border p-4 md:flex-row md:items-center md:justify-between"
            >
              <div className="space-y-1">
                <div className="font-medium">{skill.name}</div>
                <div className="text-muted-foreground text-sm">
                  {skill.description || skill.type || skill.id}
                </div>
              </div>
              <div className="flex gap-2">
                <Button variant="outline" asChild>
                  <Link href={`/workspace/bots/${bot.id}/skills/${skill.id}`}>
                    {page_bot('edit')}
                  </Link>
                </Button>
                <Button
                  variant="outline"
                  onClick={() => handleDelete(skill.id)}
                >
                  {page_bot('delete')}
                </Button>
              </div>
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
};
