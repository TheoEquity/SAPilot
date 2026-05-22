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
import type { BotConfigWithOrchestration } from './orchestration-types';
import { getFlowDiagnostics } from './flow-utils';

export const BotOrchestrationCard = () => {
  const { bot } = useBotConfigContext();
  const page_bot = useTranslations('page_bot');
  const botConfig = (bot.config || {}) as BotConfigWithOrchestration;

  const intentRouter = botConfig.orchestration?.intent_router;
  const skills = botConfig.orchestration?.skills || [];
  const skillsCount = skills.length;
  const intentRouterNodes = intentRouter?.flow?.nodes?.length || 0;
  const intentRouterEdges = intentRouter?.flow?.edges?.length || 0;
  const candidateSkillsCount = intentRouter?.candidate_skills?.length || 0;
  const routerDiagnostics = getFlowDiagnostics(intentRouter?.flow);
  const enabledSkillsCount = skills.filter((skill) => skill.enabled !== false).length;
  const skillFlowCount = skills.filter(
    (skill) => (skill.flow?.nodes?.length || 0) > 0 || (skill.flow?.edges?.length || 0) > 0,
  ).length;
  const invalidCandidateCount = (intentRouter?.candidate_skills || []).filter(
    (candidate) => !skills.some((skill) => skill.id === candidate.skill_id),
  ).length;
  const summaryItems = [
    page_bot('orchestration_summary_skills', { count: String(skillsCount) }),
    page_bot('orchestration_summary_enabled_skills', { count: String(enabledSkillsCount) }),
    page_bot('orchestration_summary_skill_flows', { count: String(skillFlowCount) }),
  ];
  const routerSummaryItems = [
    page_bot('orchestration_summary_candidates', { count: String(candidateSkillsCount) }),
    page_bot('orchestration_summary_nodes', { count: String(intentRouterNodes) }),
    page_bot('orchestration_summary_edges', { count: String(intentRouterEdges) }),
  ];
  const routerHealthItems = [
    page_bot('orchestration_summary_start_nodes', {
      count: String(routerDiagnostics.startNodeIds.length),
    }),
    page_bot('orchestration_summary_isolated_nodes', {
      count: String(routerDiagnostics.isolatedNodeIds.length),
    }),
    page_bot('orchestration_summary_invalid_candidates', {
      count: String(invalidCandidateCount),
    }),
    page_bot('orchestration_summary_fallback_ready', {
      status: intentRouter?.fallback_skill_id ? page_bot('orchestration_configured') : page_bot('orchestration_not_configured'),
    }),
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle>{page_bot('orchestration_title')}</CardTitle>
        <CardDescription>{page_bot('orchestration_description')}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4 pt-6">
        <div className="flex flex-col gap-3 rounded-lg border p-4 md:flex-row md:items-center md:justify-between">
          <div className="space-y-1">
            <div className="font-medium">{page_bot('intent_router_title')}</div>
            <div className="text-muted-foreground text-sm">
              {page_bot('intent_router_description')}
            </div>
            <div className="text-muted-foreground text-sm">
              {intentRouter?.id
                ? page_bot('orchestration_configured')
                : page_bot('orchestration_not_configured')}
            </div>
            <div className="text-muted-foreground text-xs">
              {routerSummaryItems.join(' · ')}
            </div>
            <div className="text-muted-foreground text-xs">
              {routerHealthItems.join(' · ')}
            </div>
          </div>
          <Button asChild variant="outline">
            <Link href={`/workspace/bots/${bot.id}/intent-router`}>
              {page_bot('orchestration_open')}
            </Link>
          </Button>
        </div>

        <div className="flex flex-col gap-3 rounded-lg border p-4 md:flex-row md:items-center md:justify-between">
          <div className="space-y-1">
            <div className="font-medium">{page_bot('skills_title')}</div>
            <div className="text-muted-foreground text-sm">
              {page_bot('skills_description')}
            </div>
            <div className="text-muted-foreground text-sm">
              {skillsCount > 0
                ? page_bot('skills_configured', { count: String(skillsCount) })
                : page_bot('orchestration_not_configured')}
            </div>
            <div className="text-muted-foreground text-xs">{summaryItems.join(' · ')}</div>
          </div>
          <Button asChild variant="outline">
            <Link href={`/workspace/bots/${bot.id}/skills`}>
              {page_bot('orchestration_open')}
            </Link>
          </Button>
        </div>
      </CardContent>
    </Card>
  );
};
