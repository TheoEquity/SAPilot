import type { ReactFlowEdge, ReactFlowNode, ReactFlowSchema } from './orchestration-types';

export type FlowValidationIssue =
  | { code: 'parse_error' }
  | { code: 'duplicate_node_id'; nodeId: string }
  | { code: 'missing_edge_source'; edgeId: string; source: string }
  | { code: 'missing_edge_target'; edgeId: string; target: string }
  | { code: 'invalid_zoom'; zoom: number };

export type FlowDiagnostics = {
  startNodeIds: string[];
  isolatedNodeIds: string[];
  danglingNodeIds: string[];
  weakConditionNodeIds: string[];
};

export const EMPTY_FLOW: ReactFlowSchema = {
  version: '1.0.0',
  viewport: { x: 0, y: 0, zoom: 1 },
  nodes: [],
  edges: [],
};

export const normalizeFlowSchema = (flow?: ReactFlowSchema): ReactFlowSchema => ({
  version: flow?.version || EMPTY_FLOW.version,
  viewport: flow?.viewport || EMPTY_FLOW.viewport,
  nodes: flow?.nodes || [],
  edges: flow?.edges || [],
});

export const getStartNodeIds = (nodes: ReactFlowNode[], edges: ReactFlowEdge[]) => {
  const indegree = new Map(nodes.map((node) => [node.id, 0]));

  edges.forEach((edge) => {
    if (!indegree.has(edge.target) || !indegree.has(edge.source) || edge.source === edge.target) {
      return;
    }

    indegree.set(edge.target, (indegree.get(edge.target) || 0) + 1);
  });

  return nodes.filter((node) => (indegree.get(node.id) || 0) === 0).map((node) => node.id);
};

export const getFlowDiagnostics = (flow?: ReactFlowSchema): FlowDiagnostics => {
  const normalizedFlow = normalizeFlowSchema(flow);
  const nodeIds = new Set(normalizedFlow.nodes.map((node) => node.id));
  const startNodeIds = getStartNodeIds(normalizedFlow.nodes, normalizedFlow.edges);
  const incomingCount = new Map(normalizedFlow.nodes.map((node) => [node.id, 0]));
  const outgoingCount = new Map(normalizedFlow.nodes.map((node) => [node.id, 0]));

  normalizedFlow.edges.forEach((edge) => {
    if (nodeIds.has(edge.source)) {
      outgoingCount.set(edge.source, (outgoingCount.get(edge.source) || 0) + 1);
    }

    if (nodeIds.has(edge.target)) {
      incomingCount.set(edge.target, (incomingCount.get(edge.target) || 0) + 1);
    }
  });

  return {
    startNodeIds,
    isolatedNodeIds: normalizedFlow.nodes
      .filter(
        (node) =>
          (incomingCount.get(node.id) || 0) === 0 && (outgoingCount.get(node.id) || 0) === 0,
      )
      .map((node) => node.id),
    danglingNodeIds: normalizedFlow.nodes
      .filter(
        (node) => node.type !== 'end' && (outgoingCount.get(node.id) || 0) === 0,
      )
      .map((node) => node.id),
    weakConditionNodeIds: normalizedFlow.nodes
      .filter(
        (node) => node.type === 'condition' && (outgoingCount.get(node.id) || 0) < 2,
      )
      .map((node) => node.id),
  };
};

export const validateFlowSchema = (flow?: ReactFlowSchema): FlowValidationIssue[] => {
  const normalizedFlow = normalizeFlowSchema(flow);
  const issues: FlowValidationIssue[] = [];
  const seenNodeIds = new Set<string>();
  const nodeIds = new Set(normalizedFlow.nodes.map((node) => node.id));
  const zoom = normalizedFlow.viewport?.zoom ?? 1;

  normalizedFlow.nodes.forEach((node) => {
    if (seenNodeIds.has(node.id)) {
      issues.push({ code: 'duplicate_node_id', nodeId: node.id });
      return;
    }

    seenNodeIds.add(node.id);
  });

  normalizedFlow.edges.forEach((edge) => {
    if (!nodeIds.has(edge.source)) {
      issues.push({ code: 'missing_edge_source', edgeId: edge.id, source: edge.source });
    }

    if (!nodeIds.has(edge.target)) {
      issues.push({ code: 'missing_edge_target', edgeId: edge.id, target: edge.target });
    }
  });

  if (zoom < 0.5 || zoom > 1.6) {
    issues.push({ code: 'invalid_zoom', zoom });
  }

  return issues;
};
