'use client';

import { useEffect, useMemo, useState } from 'react';

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { FormControl, FormItem, FormLabel } from '@/components/ui/form';
import { Textarea } from '@/components/ui/textarea';
import { useTranslations } from 'next-intl';
import type { ReactFlowSchema } from './orchestration-types';
import { normalizeFlowSchema, validateFlowSchema } from './flow-utils';

const formatJson = (value: unknown) => JSON.stringify(value, null, 2);

export const FlowJsonEditor = ({
  title,
  description,
  value,
  onChange,
}: {
  title: string;
  description: string;
  value?: ReactFlowSchema;
  onChange: (value: ReactFlowSchema) => void;
}) => {
  const page_bot = useTranslations('page_bot');
  const [viewportJson, setViewportJson] = useState('');
  const [nodesJson, setNodesJson] = useState('');
  const [edgesJson, setEdgesJson] = useState('');
  const [issues, setIssues] = useState<string[]>([]);

  const normalizedValue = useMemo(() => normalizeFlowSchema(value), [value]);

  useEffect(() => {
    setViewportJson(formatJson(normalizedValue.viewport));
    setNodesJson(formatJson(normalizedValue.nodes));
    setEdgesJson(formatJson(normalizedValue.edges));
  }, [normalizedValue]);

  const syncFlow = ({
    nextViewportJson = viewportJson,
    nextNodesJson = nodesJson,
    nextEdgesJson = edgesJson,
  }: {
    nextViewportJson?: string;
    nextNodesJson?: string;
    nextEdgesJson?: string;
  }) => {
    try {
      const nextFlow = normalizeFlowSchema({
        ...normalizedValue,
        viewport: JSON.parse(nextViewportJson),
        nodes: JSON.parse(nextNodesJson),
        edges: JSON.parse(nextEdgesJson),
      });
      const nextIssues = validateFlowSchema(nextFlow).map((issue) => {
        switch (issue.code) {
          case 'duplicate_node_id':
            return page_bot('flow_issue_duplicate_node_id', { nodeId: issue.nodeId });
          case 'missing_edge_source':
            return page_bot('flow_issue_missing_edge_source', {
              edgeId: issue.edgeId,
              source: issue.source,
            });
          case 'missing_edge_target':
            return page_bot('flow_issue_missing_edge_target', {
              edgeId: issue.edgeId,
              target: issue.target,
            });
          case 'invalid_zoom':
            return page_bot('flow_issue_invalid_zoom', { zoom: String(issue.zoom) });
          default:
            return page_bot('flow_json_invalid');
        }
      });

      setIssues(nextIssues);
      onChange(nextFlow);
    } catch {
      setIssues([page_bot('flow_json_invalid')]);
      return;
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <FormItem>
          <FormLabel>Viewport</FormLabel>
          <FormControl>
            <Textarea
              className="h-28 font-mono text-sm"
              aria-invalid={issues.length > 0}
              value={viewportJson}
              onChange={(event) => {
                const nextValue = event.target.value;
                setViewportJson(nextValue);
                syncFlow({ nextViewportJson: nextValue });
              }}
              placeholder={page_bot('flow_viewport_placeholder')}
            />
          </FormControl>
        </FormItem>

        <FormItem>
          <FormLabel>Nodes</FormLabel>
          <FormControl>
            <Textarea
              className="h-40 font-mono text-sm"
              aria-invalid={issues.length > 0}
              value={nodesJson}
              onChange={(event) => {
                const nextValue = event.target.value;
                setNodesJson(nextValue);
                syncFlow({ nextNodesJson: nextValue });
              }}
              placeholder={page_bot('flow_nodes_placeholder')}
            />
          </FormControl>
        </FormItem>

        <FormItem>
          <FormLabel>Edges</FormLabel>
          <FormControl>
            <Textarea
              className="h-40 font-mono text-sm"
              aria-invalid={issues.length > 0}
              value={edgesJson}
              onChange={(event) => {
                const nextValue = event.target.value;
                setEdgesJson(nextValue);
                syncFlow({ nextEdgesJson: nextValue });
              }}
              placeholder={page_bot('flow_edges_placeholder')}
            />
          </FormControl>
        </FormItem>

        {issues.length > 0 ? (
          <div className="text-destructive flex flex-col gap-1 text-sm">
            {issues.map((issue) => (
              <p key={issue}>{issue}</p>
            ))}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
};
