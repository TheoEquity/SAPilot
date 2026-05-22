'use client';

import { useEffect, useMemo, useRef, useState } from 'react';

import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { useTranslations } from 'next-intl';
import type { ReactFlowEdge, ReactFlowNode, ReactFlowSchema } from './orchestration-types';
import { getFlowDiagnostics, getStartNodeIds } from './flow-utils';

const CANVAS_WIDTH = 960;
const CANVAS_HEIGHT = 420;
const NODE_WIDTH = 148;
const NODE_HEIGHT = 56;
const MIN_ZOOM = 0.5;
const MAX_ZOOM = 1.6;
const ZOOM_STEP = 0.1;

const NODE_TYPE_OPTIONS = ['default', 'intent', 'skill', 'condition', 'end'] as const;

const NODE_TYPE_CLASSNAME: Record<(typeof NODE_TYPE_OPTIONS)[number], string> = {
  default: 'border-border bg-background',
  intent: 'border-sky-300 bg-sky-50 dark:border-sky-800 dark:bg-sky-950/40',
  skill: 'border-emerald-300 bg-emerald-50 dark:border-emerald-800 dark:bg-emerald-950/40',
  condition: 'border-amber-300 bg-amber-50 dark:border-amber-800 dark:bg-amber-950/40',
  end: 'border-violet-300 bg-violet-50 dark:border-violet-800 dark:bg-violet-950/40',
};

const clamp = (value: number, min: number, max: number) =>
  Math.min(Math.max(value, min), max);

const roundZoom = (value: number) => Math.round(value * 100) / 100;

const createNodeId = (nodes: ReactFlowNode[]) => {
  let nextIndex = nodes.length + 1;

  while (nodes.some((node) => node.id === `node_${nextIndex}`)) {
    nextIndex += 1;
  }

  return `node_${nextIndex}`;
};

const createEdgeId = (edges: ReactFlowEdge[]) => {
  let nextIndex = edges.length + 1;

  while (edges.some((edge) => edge.id === `edge_${nextIndex}`)) {
    nextIndex += 1;
  }

  return `edge_${nextIndex}`;
};

const getNodeNote = (node: ReactFlowNode) => String(node.data?.note || '');

const layoutNodes = (nodes: ReactFlowNode[], edges: ReactFlowEdge[]) => {
  const horizontalGap = 72;
  const verticalGap = 36;
  const startX = 32;
  const startY = 32;
  const nodeMap = new Map(nodes.map((node) => [node.id, node]));
  const outgoing = new Map<string, string[]>();
  const indegree = new Map<string, number>();
  const levels = new Map<string, number>();

  nodes.forEach((node) => {
    outgoing.set(node.id, []);
    indegree.set(node.id, 0);
  });

  edges.forEach((edge) => {
    if (!nodeMap.has(edge.source) || !nodeMap.has(edge.target) || edge.source === edge.target) {
      return;
    }

    outgoing.set(edge.source, [...(outgoing.get(edge.source) || []), edge.target]);
    indegree.set(edge.target, (indegree.get(edge.target) || 0) + 1);
  });

  const queue = nodes
    .filter((node) => (indegree.get(node.id) || 0) === 0)
    .sort((a, b) => a.position.y - b.position.y || a.position.x - b.position.x)
    .map((node) => node.id);

  queue.forEach((nodeId) => levels.set(nodeId, 0));

  for (let index = 0; index < queue.length; index += 1) {
    const nodeId = queue[index];
    const currentLevel = levels.get(nodeId) || 0;

    (outgoing.get(nodeId) || []).forEach((targetId) => {
      levels.set(targetId, Math.max(levels.get(targetId) || 0, currentLevel + 1));
      indegree.set(targetId, (indegree.get(targetId) || 0) - 1);

      if ((indegree.get(targetId) || 0) === 0) {
        queue.push(targetId);
      }
    });
  }

  // For cycles or isolated groups, keep assigning the next available column.
  nodes.forEach((node) => {
    if (!levels.has(node.id)) {
      levels.set(node.id, 0);
    }
  });

  const grouped = new Map<number, ReactFlowNode[]>();

  nodes.forEach((node) => {
    const level = levels.get(node.id) || 0;
    grouped.set(level, [...(grouped.get(level) || []), node]);
  });

  return Array.from(grouped.entries())
    .sort(([leftLevel], [rightLevel]) => leftLevel - rightLevel)
    .flatMap(([level, levelNodes]) =>
      levelNodes
        .sort((leftNode, rightNode) => leftNode.position.y - rightNode.position.y)
        .map((node, row) => ({
          ...node,
          position: {
            x: clamp(startX + level * (NODE_WIDTH + horizontalGap), 0, CANVAS_WIDTH - NODE_WIDTH),
            y: clamp(startY + row * (NODE_HEIGHT + verticalGap), 0, CANVAS_HEIGHT - NODE_HEIGHT),
          },
        })),
    );
};

export const FlowCanvasEditor = ({
  title,
  description,
  value,
  onChange,
  skillOptions = [],
}: {
  title: string;
  description: string;
  value: ReactFlowSchema;
  onChange: (value: ReactFlowSchema) => void;
  skillOptions?: Array<{ id: string; label: string }>;
}) => {
  const page_bot = useTranslations('page_bot');
  const canvasRef = useRef<HTMLDivElement | null>(null);
  const dragRef = useRef<{
    nodeId: string;
    offsetX: number;
    offsetY: number;
  } | null>(null);
  const panRef = useRef<{
    startX: number;
    startY: number;
    originX: number;
    originY: number;
  } | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState('');
  const [selectedEdgeId, setSelectedEdgeId] = useState('');
  const [edgeSourceId, setEdgeSourceId] = useState('');
  const [edgeTargetId, setEdgeTargetId] = useState('');
  const [newNodeLabel, setNewNodeLabel] = useState('');
  const [newNodeType, setNewNodeType] = useState<(typeof NODE_TYPE_OPTIONS)[number]>('default');
  const [nodeSearchId, setNodeSearchId] = useState('');

  const nodes = value.nodes || [];
  const edges = value.edges || [];
  const diagnostics = useMemo(() => getFlowDiagnostics(value), [value]);
  const startNodeIds = useMemo(() => new Set(getStartNodeIds(nodes, edges)), [edges, nodes]);

  const selectedNode = useMemo(
    () => nodes.find((node) => node.id === selectedNodeId),
    [nodes, selectedNodeId],
  );

  const selectedEdge = useMemo(
    () => edges.find((edge) => edge.id === selectedEdgeId),
    [edges, selectedEdgeId],
  );

  const selectedNodeConnectedEdgesCount = useMemo(() => {
    if (!selectedNode) {
      return 0;
    }

    return edges.filter(
      (edge) => edge.source === selectedNode.id || edge.target === selectedNode.id,
    ).length;
  }, [edges, selectedNode]);

  const focusNode = (nodeId: string) => {
    const node = nodes.find((item) => item.id === nodeId);

    if (!node) {
      return;
    }

    const zoom = value.viewport?.zoom || 1;
    const targetX = clamp(CANVAS_WIDTH / 2 - (node.position.x + NODE_WIDTH / 2) * zoom, -CANVAS_WIDTH, CANVAS_WIDTH);
    const targetY = clamp(CANVAS_HEIGHT / 2 - (node.position.y + NODE_HEIGHT / 2) * zoom, -CANVAS_HEIGHT, CANVAS_HEIGHT);

    setSelectedNodeId(node.id);
    updateViewport({
      ...(value.viewport || { x: 0, y: 0, zoom: 1 }),
      x: targetX,
      y: targetY,
      zoom,
    });
  };

  useEffect(() => {
    if (selectedNodeId && !nodes.some((node) => node.id === selectedNodeId)) {
      setSelectedNodeId('');
    }

    if (edgeSourceId && !nodes.some((node) => node.id === edgeSourceId)) {
      setEdgeSourceId('');
    }

    if (edgeTargetId && !nodes.some((node) => node.id === edgeTargetId)) {
      setEdgeTargetId('');
    }

    if (selectedEdgeId && !edges.some((edge) => edge.id === selectedEdgeId)) {
      setSelectedEdgeId('');
    }
  }, [edgeSourceId, edgeTargetId, edges, nodes, selectedEdgeId, selectedNodeId]);

  useEffect(() => {
    const handlePointerMove = (event: PointerEvent) => {
      if (!dragRef.current || !canvasRef.current) {
        return;
      }

      const rect = canvasRef.current.getBoundingClientRect();
      const viewportX = value.viewport?.x || 0;
      const viewportY = value.viewport?.y || 0;
      const zoom = value.viewport?.zoom || 1;
      const x = clamp(
        (event.clientX - rect.left - dragRef.current.offsetX - viewportX) / zoom,
        0,
        CANVAS_WIDTH - NODE_WIDTH,
      );
      const y = clamp(
        (event.clientY - rect.top - dragRef.current.offsetY - viewportY) / zoom,
        0,
        CANVAS_HEIGHT - NODE_HEIGHT,
      );

      onChange({
        ...value,
        nodes: nodes.map((node) =>
          node.id === dragRef.current?.nodeId
            ? {
                ...node,
                position: { x, y },
              }
            : node,
        ),
      });
    };

    const handlePanMove = (event: PointerEvent) => {
      if (!panRef.current) {
        return;
      }

      onChange({
        ...value,
        viewport: {
          ...(value.viewport || { x: 0, y: 0, zoom: 1 }),
          x: panRef.current.originX + event.clientX - panRef.current.startX,
          y: panRef.current.originY + event.clientY - panRef.current.startY,
          zoom: value.viewport?.zoom || 1,
        },
      });
    };

    const handlePointerUp = () => {
      dragRef.current = null;
      panRef.current = null;
    };

    window.addEventListener('pointermove', handlePointerMove);
    window.addEventListener('pointermove', handlePanMove);
    window.addEventListener('pointerup', handlePointerUp);

    return () => {
      window.removeEventListener('pointermove', handlePointerMove);
      window.removeEventListener('pointermove', handlePanMove);
      window.removeEventListener('pointerup', handlePointerUp);
    };
  }, [nodes, onChange, value]);

  const handleAddNode = () => {
    const nextId = createNodeId(nodes);
    const nextNode: ReactFlowNode = {
      id: nextId,
      type: newNodeType,
      position: {
        x: 40 + ((nodes.length * 36) % 360),
        y: 40 + ((nodes.length * 28) % 220),
      },
      data: {
        label: newNodeLabel.trim() || nextId,
      },
    };

    onChange({
      ...value,
      nodes: [...nodes, nextNode],
    });
    setNewNodeLabel('');
    setNewNodeType('default');
    focusNode(nextId);
  };

  const handleDeleteNode = () => {
    if (!selectedNodeId) {
      return;
    }

    if (
      selectedNodeConnectedEdgesCount > 0 &&
      !window.confirm(
        page_bot('flow_delete_node_confirm', {
          count: String(selectedNodeConnectedEdgesCount),
        }),
      )
    ) {
      return;
    }

    onChange({
      ...value,
      nodes: nodes.filter((node) => node.id !== selectedNodeId),
      edges: edges.filter(
        (edge) => edge.source !== selectedNodeId && edge.target !== selectedNodeId,
      ),
    });
    setSelectedNodeId('');
    setSelectedEdgeId('');
  };

  const handleDuplicateNode = () => {
    if (!selectedNode) {
      return;
    }

    const nextId = createNodeId(nodes);
    const nextNode: ReactFlowNode = {
      ...selectedNode,
      id: nextId,
      position: {
        x: clamp(selectedNode.position.x + 32, 0, CANVAS_WIDTH - NODE_WIDTH),
        y: clamp(selectedNode.position.y + 32, 0, CANVAS_HEIGHT - NODE_HEIGHT),
      },
      data: {
        ...selectedNode.data,
        label: `${String(selectedNode.data?.label || selectedNode.id)} Copy`,
      },
    };
    const duplicatedEdges = edges
      .filter((edge) => edge.source === selectedNode.id)
      .reduce<ReactFlowEdge[]>((result, edge) => {
        result.push({
          ...edge,
          id: createEdgeId([...edges, ...result]),
          source: nextId,
        });

        return result;
      }, []);

    onChange({
      ...value,
      nodes: [...nodes, nextNode],
      edges: [...edges, ...duplicatedEdges],
    });
    focusNode(nextId);
  };

  const handleAddEdge = () => {
    if (!edgeSourceId || !edgeTargetId || edgeSourceId === edgeTargetId) {
      return;
    }

    if (
      edges.some(
        (edge) => edge.source === edgeSourceId && edge.target === edgeTargetId,
      )
    ) {
      return;
    }

    const sourceNode = nodes.find((node) => node.id === edgeSourceId);

    if (sourceNode?.type === 'end') {
      return;
    }

    onChange({
      ...value,
      edges: [
        ...edges,
        {
          id: createEdgeId(edges),
          source: edgeSourceId,
          target: edgeTargetId,
          type: 'default',
          data: {
            label: `${edgeSourceId} -> ${edgeTargetId}`,
          },
        },
      ],
    });
  };

  const handleDeleteEdge = (edgeId: string) => {
    onChange({
      ...value,
      edges: edges.filter((edge) => edge.id !== edgeId),
    });

    if (selectedEdgeId === edgeId) {
      setSelectedEdgeId('');
    }
  };

  const updateViewport = (nextViewport: ReactFlowSchema['viewport']) => {
    onChange({
      ...value,
      viewport: {
        x: nextViewport?.x || 0,
        y: nextViewport?.y || 0,
        zoom: nextViewport?.zoom || 1,
      },
    });
  };

  const handleRenameSelectedNode = (label: string) => {
    if (!selectedNode) {
      return;
    }

    onChange({
      ...value,
      nodes: nodes.map((node) =>
        node.id === selectedNode.id
          ? {
              ...node,
              data: {
                ...node.data,
                label,
              },
            }
          : node,
      ),
    });
  };

  const handleChangeSelectedNodeType = (type: string) => {
    if (!selectedNode || !NODE_TYPE_OPTIONS.includes(type as (typeof NODE_TYPE_OPTIONS)[number])) {
      return;
    }

    onChange({
      ...value,
      nodes: nodes.map((node) =>
        node.id === selectedNode.id
          ? {
              ...node,
              type,
            }
          : node,
      ),
    });
  };

  const handleChangeSelectedNodeNote = (note: string) => {
    if (!selectedNode) {
      return;
    }

    onChange({
      ...value,
      nodes: nodes.map((node) =>
        node.id === selectedNode.id
          ? {
              ...node,
              data: {
                ...node.data,
                note,
              },
            }
          : node,
      ),
    });
  };

  const handleRenameSelectedEdge = (label: string) => {
    if (!selectedEdge) {
      return;
    }

    onChange({
      ...value,
      edges: edges.map((edge) =>
        edge.id === selectedEdge.id
          ? {
              ...edge,
              data: {
                ...edge.data,
                label,
              },
            }
          : edge,
      ),
    });
  };

  const handleChangeSelectedEdgeCondition = (condition: string) => {
    if (!selectedEdge) {
      return;
    }

    onChange({
      ...value,
      edges: edges.map((edge) =>
        edge.id === selectedEdge.id
          ? {
              ...edge,
              data: {
                ...edge.data,
                condition,
              },
            }
          : edge,
      ),
    });
  };

  const handleZoomIn = () => {
    updateViewport({
      ...(value.viewport || { x: 0, y: 0, zoom: 1 }),
      zoom: roundZoom(clamp((value.viewport?.zoom || 1) + ZOOM_STEP, MIN_ZOOM, MAX_ZOOM)),
    });
  };

  const handleZoomOut = () => {
    updateViewport({
      ...(value.viewport || { x: 0, y: 0, zoom: 1 }),
      zoom: roundZoom(clamp((value.viewport?.zoom || 1) - ZOOM_STEP, MIN_ZOOM, MAX_ZOOM)),
    });
  };

  const handleResetViewport = () => {
    updateViewport({ x: 0, y: 0, zoom: 1 });
  };

  const handleAutoLayout = () => {
    const nextNodes = layoutNodes(nodes, edges);

    onChange({
      ...value,
      nodes: nextNodes,
    });

    if (nextNodes[0]) {
      focusNode(nextNodes[0].id);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end">
          <div className="flex-1">
            <div className="mb-2 text-sm font-medium">
              {page_bot('flow_new_node_label')}
            </div>
            <Input
              value={newNodeLabel}
              onChange={(event) => setNewNodeLabel(event.target.value)}
              placeholder={page_bot('flow_new_node_placeholder')}
            />
          </div>
          <div className="w-full lg:w-52">
            <div className="mb-2 text-sm font-medium">
              {page_bot('flow_new_node_type')}
            </div>
            <Select value={newNodeType} onValueChange={(value) => setNewNodeType(value as (typeof NODE_TYPE_OPTIONS)[number])}>
              <SelectTrigger>
                <SelectValue placeholder={page_bot('flow_node_type_placeholder')} />
              </SelectTrigger>
              <SelectContent>
                {NODE_TYPE_OPTIONS.map((type) => (
                  <SelectItem key={type} value={type}>
                    {page_bot(`flow_node_type_${type}`)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Button type="button" variant="outline" onClick={handleAddNode}>
            {page_bot('flow_add_node')}
          </Button>
          <Button type="button" variant="outline" onClick={handleAutoLayout} disabled={nodes.length < 2}>
            {page_bot('flow_auto_layout')}
          </Button>
          <Button
            type="button"
            variant="outline"
            onClick={handleDuplicateNode}
            disabled={!selectedNode}
          >
            {page_bot('flow_duplicate_node')}
          </Button>
          <Button
            type="button"
            variant="outline"
            onClick={handleDeleteNode}
            disabled={!selectedNodeId}
          >
            {page_bot('flow_delete_node')}
          </Button>
        </div>

        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
          <div
            ref={canvasRef}
            className="bg-muted/30 relative overflow-hidden rounded-xl border"
            style={{ minHeight: `${CANVAS_HEIGHT}px` }}
            onPointerDown={(event) => {
              if (event.target !== event.currentTarget) {
                return;
              }

              panRef.current = {
                startX: event.clientX,
                startY: event.clientY,
                originX: value.viewport?.x || 0,
                originY: value.viewport?.y || 0,
              };
            }}
          >
            <div
              className="absolute inset-0"
              style={{
                transform: `translate(${value.viewport?.x || 0}px, ${value.viewport?.y || 0}px) scale(${value.viewport?.zoom || 1})`,
                transformOrigin: 'top left',
              }}
            >
              <svg className="absolute inset-0 h-full w-full overflow-visible">
                {edges.map((edge) => {
                  const sourceNode = nodes.find((node) => node.id === edge.source);
                  const targetNode = nodes.find((node) => node.id === edge.target);

                  if (!sourceNode || !targetNode) {
                    return null;
                  }

                  const x1 = sourceNode.position.x + NODE_WIDTH / 2;
                  const y1 = sourceNode.position.y + NODE_HEIGHT / 2;
                  const x2 = targetNode.position.x + NODE_WIDTH / 2;
                  const y2 = targetNode.position.y + NODE_HEIGHT / 2;

                  return (
                    <g key={edge.id}>
                      <line
                        x1={x1}
                        y1={y1}
                        x2={x2}
                        y2={y2}
                        stroke="currentColor"
                        strokeOpacity={edge.id === selectedEdgeId ? '0.7' : '0.35'}
                        strokeWidth={edge.id === selectedEdgeId ? '3' : '2'}
                        onClick={() => setSelectedEdgeId(edge.id)}
                      />
                      <text
                        x={(x1 + x2) / 2}
                        y={(y1 + y2) / 2 - 6}
                        textAnchor="middle"
                        className="fill-foreground text-xs"
                      >
                        {String(edge.data?.label || '')}
                      </text>
                      {edge.data?.condition ? (
                        <text
                          x={(x1 + x2) / 2}
                          y={(y1 + y2) / 2 + 10}
                          textAnchor="middle"
                          className="fill-muted-foreground text-xs"
                        >
                          {String(edge.data.condition)}
                        </text>
                      ) : null}
                    </g>
                  );
                })}
              </svg>

              {nodes.map((node) => {
                const isSelected = node.id === selectedNodeId;
                const isStartNode = startNodeIds.has(node.id);

                return (
                  <button
                    key={node.id}
                    type="button"
                    className={[
                      'absolute rounded-lg border px-3 py-2 text-left shadow-sm transition',
                      NODE_TYPE_CLASSNAME[(node.type as (typeof NODE_TYPE_OPTIONS)[number]) || 'default'],
                      isSelected ? 'ring-primary/20 ring-4' : '',
                    ].join(' ')}
                    style={{
                      left: `${node.position.x}px`,
                      top: `${node.position.y}px`,
                      width: `${NODE_WIDTH}px`,
                      height: `${NODE_HEIGHT}px`,
                    }}
                    onClick={() => setSelectedNodeId(node.id)}
                    onPointerDown={(event) => {
                      const rect = event.currentTarget.getBoundingClientRect();
                      const zoom = value.viewport?.zoom || 1;
                      dragRef.current = {
                        nodeId: node.id,
                        offsetX: (event.clientX - rect.left) / zoom,
                        offsetY: (event.clientY - rect.top) / zoom,
                      };
                      setSelectedNodeId(node.id);
                    }}
                  >
                    {isStartNode ? (
                      <div className="mb-1 inline-flex rounded-full bg-sky-100 px-2 py-0.5 text-[10px] font-medium text-sky-700 dark:bg-sky-950/60 dark:text-sky-200">
                        {page_bot('flow_start_node_badge')}
                      </div>
                    ) : null}
                    <div className="truncate text-sm font-medium">
                      {String(node.data?.label || node.id)}
                    </div>
                    <div className="text-muted-foreground truncate text-xs">
                      {node.type || 'default'} · {node.id}
                    </div>
                    {getNodeNote(node) ? (
                      <div className="text-muted-foreground mt-1 line-clamp-2 text-[11px] leading-4">
                        {getNodeNote(node)}
                      </div>
                    ) : null}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="flex flex-col gap-4 rounded-xl border p-4">
            <div className="flex items-center gap-2">
              <Button type="button" variant="outline" size="sm" onClick={handleZoomOut}>
                {page_bot('flow_zoom_out')}
              </Button>
              <Button type="button" variant="outline" size="sm" onClick={handleZoomIn}>
                {page_bot('flow_zoom_in')}
              </Button>
              <Button type="button" variant="outline" size="sm" onClick={handleResetViewport}>
                {page_bot('flow_reset_viewport')}
              </Button>
            </div>

            <div>
              <div className="mb-2 text-sm font-medium">{page_bot('flow_node_quick_jump')}</div>
              <Select
                value={nodeSearchId}
                onValueChange={(value) => {
                  setNodeSearchId(value);
                  focusNode(value);
                }}
              >
                <SelectTrigger>
                  <SelectValue placeholder={page_bot('flow_node_quick_jump_placeholder')} />
                </SelectTrigger>
                <SelectContent>
                  {nodes.map((node) => (
                    <SelectItem key={node.id} value={node.id}>
                      {String(node.data?.label || node.id)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div>
              <div className="mb-2 text-sm font-medium">
                {page_bot('flow_connect_nodes')}
              </div>
              <div className="flex flex-col gap-3">
                <Select value={edgeSourceId} onValueChange={setEdgeSourceId}>
                  <SelectTrigger>
                    <SelectValue placeholder={page_bot('flow_edge_source_placeholder')} />
                  </SelectTrigger>
                  <SelectContent>
                    {nodes.map((node) => (
                      <SelectItem key={node.id} value={node.id}>
                        {String(node.data?.label || node.id)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>

                <Select value={edgeTargetId} onValueChange={setEdgeTargetId}>
                  <SelectTrigger>
                    <SelectValue placeholder={page_bot('flow_edge_target_placeholder')} />
                  </SelectTrigger>
                  <SelectContent>
                    {nodes.map((node) => (
                      <SelectItem key={node.id} value={node.id}>
                        {String(node.data?.label || node.id)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>

                <Button type="button" variant="outline" onClick={handleAddEdge}>
                  {page_bot('flow_add_edge')}
                </Button>
                <div className="text-muted-foreground text-xs">
                  {page_bot('flow_connect_nodes_hint')}
                </div>
              </div>
            </div>

            <div>
              <div className="mb-2 text-sm font-medium">
                {page_bot('flow_selected_node')}
              </div>
              {selectedNode ? (
                <div className="flex flex-col gap-2">
                  <div className="text-muted-foreground text-sm">
                    {selectedNode.id}
                  </div>
                  {selectedNodeConnectedEdgesCount > 0 ? (
                    <div className="text-amber-600 text-xs dark:text-amber-300">
                      {page_bot('flow_delete_node_impact', {
                        count: String(selectedNodeConnectedEdgesCount),
                      })}
                    </div>
                  ) : null}
                  <Input
                    value={String(selectedNode.data?.label || '')}
                    onChange={(event) => handleRenameSelectedNode(event.target.value)}
                    placeholder={page_bot('flow_new_node_placeholder')}
                  />
                  <Select
                    value={selectedNode.type || 'default'}
                    onValueChange={handleChangeSelectedNodeType}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder={page_bot('flow_node_type_placeholder')} />
                    </SelectTrigger>
                    <SelectContent>
                      {NODE_TYPE_OPTIONS.map((type) => (
                        <SelectItem key={type} value={type}>
                          {page_bot(`flow_node_type_${type}`)}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <div className="mb-1 mt-1 text-sm font-medium">
                    {page_bot('flow_node_note')}
                  </div>
                  <Textarea
                    value={getNodeNote(selectedNode)}
                    onChange={(event) => handleChangeSelectedNodeNote(event.target.value)}
                    placeholder={page_bot('flow_node_note_placeholder')}
                    rows={4}
                  />
                  {selectedNode.type === 'intent' ? (
                    <Input
                      value={String(selectedNode.data?.intent_key || '')}
                      onChange={(event) =>
                        onChange({
                          ...value,
                          nodes: nodes.map((node) =>
                            node.id === selectedNode.id
                              ? {
                                  ...node,
                                  data: { ...node.data, intent_key: event.target.value },
                                }
                              : node,
                          ),
                        })
                      }
                      placeholder={page_bot('flow_node_intent_key_placeholder')}
                    />
                  ) : null}
                  {selectedNode.type === 'skill' ? (
                    <Select
                      value={String(selectedNode.data?.skill_id || '')}
                      onValueChange={(selectedSkillId) =>
                        onChange({
                          ...value,
                          nodes: nodes.map((node) =>
                            node.id === selectedNode.id
                              ? {
                                  ...node,
                                  data: { ...node.data, skill_id: selectedSkillId },
                                }
                              : node,
                          ),
                        })
                      }
                    >
                      <SelectTrigger>
                        <SelectValue placeholder={page_bot('flow_node_skill_id_placeholder')} />
                      </SelectTrigger>
                      <SelectContent>
                        {skillOptions.map((skill) => (
                          <SelectItem key={skill.id} value={skill.id}>
                            {skill.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  ) : null}
                  {selectedNode.type === 'condition' ? (
                    <Input
                      value={String(selectedNode.data?.condition_group || '')}
                      onChange={(event) =>
                        onChange({
                          ...value,
                          nodes: nodes.map((node) =>
                            node.id === selectedNode.id
                              ? {
                                  ...node,
                                  data: { ...node.data, condition_group: event.target.value },
                                }
                              : node,
                          ),
                        })
                      }
                      placeholder={page_bot('flow_node_condition_group_placeholder')}
                    />
                  ) : null}
                </div>
              ) : (
                <div className="text-muted-foreground text-sm">
                  {page_bot('flow_no_node_selected')}
                </div>
              )}
            </div>

            <div>
              <div className="mb-2 text-sm font-medium">
                {page_bot('flow_viewport_title')}
              </div>
              <div className="text-muted-foreground text-sm">
                x: {Math.round(value.viewport?.x || 0)}, y: {Math.round(value.viewport?.y || 0)}, zoom:{' '}
                {value.viewport?.zoom || 1}
              </div>
            </div>

            <div>
              <div className="mb-2 text-sm font-medium">
                {page_bot('flow_selected_edge')}
              </div>
              {selectedEdge ? (
                <div className="flex flex-col gap-2">
                  <div className="text-muted-foreground text-sm">
                    {selectedEdge.source} -&gt; {selectedEdge.target}
                  </div>
                  <Input
                    value={String(selectedEdge.data?.label || '')}
                    onChange={(event) => handleRenameSelectedEdge(event.target.value)}
                    placeholder={page_bot('flow_edge_label_placeholder')}
                  />
                </div>
              ) : (
                <div className="text-muted-foreground text-sm">
                  {page_bot('flow_no_edge_selected')}
                </div>
              )}

              {selectedEdge ? (
                <div className="mt-2">
                  <Input
                    value={String(selectedEdge.data?.condition || '')}
                    onChange={(event) => handleChangeSelectedEdgeCondition(event.target.value)}
                    placeholder={page_bot('flow_edge_condition_placeholder')}
                  />
                </div>
              ) : null}
            </div>

            <div>
              <div className="mb-2 text-sm font-medium">{page_bot('flow_diagnostics_title')}</div>
              <div className="text-muted-foreground flex flex-col gap-1 text-sm">
                <div>{page_bot('flow_diagnostics_start_nodes', { count: String(diagnostics.startNodeIds.length) })}</div>
                <div>{page_bot('flow_diagnostics_isolated_nodes', { count: String(diagnostics.isolatedNodeIds.length) })}</div>
                <div>{page_bot('flow_diagnostics_dangling_nodes', { count: String(diagnostics.danglingNodeIds.length) })}</div>
                <div>{page_bot('flow_diagnostics_weak_conditions', { count: String(diagnostics.weakConditionNodeIds.length) })}</div>
              </div>
            </div>

            <div>
              <div className="mb-2 text-sm font-medium">
                {page_bot('flow_edges_title')}
              </div>
              <div className="flex flex-col gap-2">
                {edges.length === 0 ? (
                  <div className="text-muted-foreground text-sm">
                    {page_bot('flow_no_edges')}
                  </div>
                ) : (
                  edges.map((edge) => (
                    <div
                      key={edge.id}
                      className="flex items-center justify-between gap-2 rounded-md border px-3 py-2"
                    >
                      <button
                        type="button"
                        className="truncate text-left text-sm"
                        onClick={() => setSelectedEdgeId(edge.id)}
                      >
                        {String(edge.data?.label || `${edge.source} -> ${edge.target}`)}
                      </button>
                      <span className="text-muted-foreground truncate text-xs">
                        {edge.source} -&gt; {edge.target}
                      </span>
                  <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDeleteEdge(edge.id)}
                      >
                        {page_bot('delete')}
                      </Button>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};
