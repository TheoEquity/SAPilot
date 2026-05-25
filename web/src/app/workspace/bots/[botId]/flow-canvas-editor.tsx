'use client';

import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import type {
  Connection,
  Edge,
  EdgeChange,
  Node,
  NodeChange,
  NodeTypes,
} from 'reactflow';
import ReactFlow, {
  addEdge,
  applyEdgeChanges,
  applyNodeChanges,
  Background,
  Controls,
  Handle,
  MarkerType,
  Position,
} from 'reactflow';
import 'reactflow/dist/style.css';

import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { useTranslations } from 'next-intl';
import { toast } from 'sonner';
import { buildEdgeId, normalizeFlowSchema } from './flow-utils';
import type { ReactFlowEdge, ReactFlowSchema } from './orchestration-types';

export const FlowCanvasEditor = ({
  title,
  description,
  value,
  onChange,
  skillOptions,
  skillTools = [],
  onQuickSave,
  mode = 'skill',
}: {
  title: string;
  description: string;
  value: ReactFlowSchema;
  onChange: (value: ReactFlowSchema) => void;
  skillOptions?: Array<{ id: string; label: string }>;
  skillTools?: Array<{ id: string; name: string; description?: string }>;
  onQuickSave?: (value: ReactFlowSchema) => Promise<boolean>;
  mode?: 'skill' | 'intent-router';
}) => {
  const normalizedValue = useMemo(() => normalizeFlowSchema(value), [value]);
  const [nodes, setNodes] = useState<Node[]>(normalizedValue?.nodes || []);
  const [edges, setEdges] = useState<Edge[]>(normalizedValue?.edges || []);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);
  const [saveState, setSaveState] = useState<'idle' | 'saving' | 'saved'>(
    'idle',
  );
  const isSavingRef = useRef(false);
  const reactFlowWrapper = useRef<HTMLDivElement>(null);
  const lastSyncedFlowRef = useRef(JSON.stringify(normalizedValue));

  const page_bot = useTranslations('page_bot');

  useEffect(() => {
    const serializedFlow = JSON.stringify(normalizedValue);
    if (serializedFlow !== lastSyncedFlowRef.current) {
      lastSyncedFlowRef.current = serializedFlow;
      setNodes(normalizedValue.nodes || []);
      setEdges(normalizedValue.edges || []);
    }
  }, [normalizedValue]);

  const onNodesChange = useCallback((changes: NodeChange[]) => {
    setNodes((nds) => applyNodeChanges(changes, nds));
    setSaveState('idle');
  }, []);

  const onEdgesChange = useCallback((changes: EdgeChange[]) => {
    setEdges((eds) => applyEdgeChanges(changes, eds));
    setSaveState('idle');
  }, []);

  const onConnect = useCallback((connection: Connection) => {
    const newEdge = {
      ...connection,
      id: buildEdgeId(connection),
      markerEnd: {
        type: MarkerType.ArrowClosed,
        width: 15,
        height: 15,
        color: '#94a3b8',
      },
      style: { strokeWidth: 2 },
    };
    setEdges((eds) => addEdge(newEdge, eds));
    setSaveState('idle');
  }, []);

  const saveToParent = useRef(setTimeout(() => {}, 0));

  const buildSchema = useCallback(
    (currNodes: Node[], currEdges: Edge[]): ReactFlowSchema => ({
      version: normalizedValue?.version || 'v2',
      nodes: currNodes.map((n) => ({
        id: n.id,
        type: n.type || 'action',
        position: n.position,
        data: n.data,
      })),
      edges: currEdges.map(
        (e): ReactFlowEdge => ({
          id: e.id,
          source: e.source,
          target: e.target,
          sourceHandle: e.sourceHandle ?? undefined,
          targetHandle: e.targetHandle ?? undefined,
          data: e.data,
        }),
      ),
    }),
    [normalizedValue?.version],
  );

  const syncChanges = useCallback(
    (currNodes: Node[], currEdges: Edge[]) => {
      clearTimeout(saveToParent.current);
      saveToParent.current = setTimeout(() => {
        const nextFlow = buildSchema(currNodes, currEdges);
        lastSyncedFlowRef.current = JSON.stringify(nextFlow);
        onChange(nextFlow);
      }, 300);
    },
    [buildSchema, onChange],
  );

  const saveNow = useCallback(async () => {
    if (isSavingRef.current) return;
    isSavingRef.current = true;
    setSaveState('saving');
    try {
      const nextFlow = buildSchema(nodes, edges);
      clearTimeout(saveToParent.current);
      lastSyncedFlowRef.current = JSON.stringify(nextFlow);
      onChange(nextFlow);
      if (onQuickSave) {
        await onQuickSave(nextFlow);
      }
      setSaveState('saved');
      toast.success(page_bot('flow_canvas_saved'));
      setTimeout(() => setSaveState('idle'), 2000);
    } catch {
      setSaveState('idle');
      toast.error(page_bot('flow_canvas_save_failed'));
    } finally {
      isSavingRef.current = false;
    }
  }, [buildSchema, edges, nodes, onChange, onQuickSave, page_bot]);

  const isMounted = useRef(false);

  useEffect(() => {
    isMounted.current = true;
    return () => {
      isMounted.current = false;
      clearTimeout(saveToParent.current);
    };
  }, []);

  useEffect(() => {
    if (isMounted.current) {
      syncChanges(nodes, edges);
    }
  }, [nodes, edges, syncChanges]);

  const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    setSelectedNodeId(node.id);
    setSelectedEdgeId(null);
  }, []);

  const onEdgeClick = useCallback((_: React.MouseEvent, edge: Edge) => {
    setSelectedEdgeId(edge.id);
    setSelectedNodeId(null);
  }, []);

  const deleteSelectedNode = useCallback(() => {
    if (!selectedNodeId) return;
    setNodes((prev) => prev.filter((n) => n.id !== selectedNodeId));
    setEdges((prev) =>
      prev.filter(
        (e) => e.source !== selectedNodeId && e.target !== selectedNodeId,
      ),
    );
    setSelectedNodeId(null);
    setSaveState('idle');
  }, [selectedNodeId]);

  const deleteSelectedEdge = useCallback(() => {
    if (!selectedEdgeId) return;
    setEdges((prev) => prev.filter((edge) => edge.id !== selectedEdgeId));
    setSelectedEdgeId(null);
    setSaveState('idle');
  }, [selectedEdgeId]);

  const addNode = useCallback(
    (type: 'start' | 'action' | 'condition' | 'end') => {
      const selectedNodePosition = nodes.find(
        (node) => node.id === selectedNodeId,
      )?.position;
      const fallbackIndex = nodes.length;
      const position = selectedNodePosition
        ? {
            x: selectedNodePosition.x + 220,
            y: selectedNodePosition.y + 40,
          }
        : {
            x: 120 + (fallbackIndex % 4) * 220,
            y: 120 + Math.floor(fallbackIndex / 4) * 140,
          };

      const id = `${type}-${Date.now()}`;
      let data: any = { label: type.charAt(0).toUpperCase() + type.slice(1) };
      if (mode === 'skill') {
        if (type === 'action')
          data = {
            ...data,
            label: page_bot('flow_canvas_default_action_label'),
            tools: [],
            prompt: '',
          };
        if (type === 'condition')
          data = {
            ...data,
            label: page_bot('flow_canvas_default_condition_label'),
            prompt: '',
            source_node_id: '',
            field: '',
            operator: 'equals',
            expected_value: 'true',
          };
      }
      if (mode === 'intent-router') {
        if (type === 'action') {
          data = {
            ...data,
            label: page_bot('intent_router_default_route_label'),
            prompt: '',
            target_skill_id: skillOptions?.[0]?.id || '',
            examples_text: '',
          };
        }
        if (type === 'condition') {
          data = {
            ...data,
            label: page_bot('intent_router_default_condition_label'),
            prompt: '',
            examples_text: '',
          };
        }
      }

      const newNodeTypeMap: Record<string, string> = {
        start: 'startEnd',
        end: 'startEnd',
        action: 'action',
        condition: 'condition',
      };

      const newNode = {
        id,
        type: newNodeTypeMap[type],
        position,
        data,
      };

      setNodes((prev) => [...prev, newNode]);
      setSaveState('idle');
    },
    [mode, nodes, page_bot, selectedNodeId, skillOptions],
  );

  const updateSelectedNodeData = useCallback(
    (updates: Record<string, any>) => {
      setNodes((nds) =>
        nds.map((node) => {
          if (node.id === selectedNodeId) {
            return { ...node, data: { ...node.data, ...updates } };
          }
          return node;
        }),
      );
      setSaveState('idle');
    },
    [selectedNodeId],
  );

  const nodeTypes: NodeTypes = useMemo(
    () => ({
      startEnd: StartEndNode,
      action: ActionNode,
      condition: ConditionNode,
    }),
    [],
  );

  const selectedNode = nodes.find((n) => n.id === selectedNodeId);
  const selectableActionNodes = useMemo(
    () => nodes.filter((node) => node.type === 'action'),
    [nodes],
  );

  return (
    <div
      className="bg-muted/5 flex h-[600px] w-full flex-col overflow-hidden rounded-lg border"
      ref={reactFlowWrapper}
    >
      <div className="bg-card flex h-10 shrink-0 items-center justify-between border-b px-4">
        <div className="flex items-center">
          <span className="text-sm font-medium">{title}</span>
          <span className="text-muted-foreground ml-2 text-xs">
            {description}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {saveState === 'saved' ? (
            <span className="animate-pulse text-xs text-green-600">
              {page_bot('flow_canvas_saved_badge')}
            </span>
          ) : (
            <span className="text-muted-foreground text-xs">
              {page_bot('flow_canvas_counts', {
                nodes: String(nodes.length),
                edges: String(edges.length),
              })}
            </span>
          )}
          <Button
            type="button"
            size="sm"
            onClick={saveNow}
            disabled={saveState === 'saving'}
            className={`${saveState === 'saved' ? 'bg-green-600 text-white' : ''}`}
          >
            {saveState === 'saving'
              ? page_bot('flow_canvas_saving')
              : saveState === 'saved'
                ? page_bot('flow_canvas_saved_short')
                : page_bot('save_bot')}
          </Button>
        </div>
      </div>

      <div
        className="relative w-full flex-1 overflow-hidden"
        style={{ width: '100%', height: '100%' }}
      >
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onNodeClick={onNodeClick}
          onEdgeClick={onEdgeClick}
          onPaneClick={() => {
            setSelectedNodeId(null);
            setSelectedEdgeId(null);
          }}
          nodeTypes={nodeTypes}
          fitView
          minZoom={0.1}
          maxZoom={1.5}
          className="bg-muted/10"
        >
          <Background gap={12} size={1} />
          <Controls showInteractive={false} />
        </ReactFlow>

        {/* Floating Add Menu */}
        <div className="absolute top-4 left-4 z-10 flex gap-1 rounded-md border bg-white/90 p-1 shadow-lg backdrop-blur supports-[backdrop-filter]:bg-white/60">
          <AddNodeBtn
            label={page_bot('flow_canvas_node_start')}
            onClick={() => addNode('start')}
            icon="▶"
            color="text-green-600"
          />
          <AddNodeBtn
            label={page_bot('flow_canvas_node_action')}
            onClick={() => addNode('action')}
            icon="⚡"
            color="text-blue-600"
          />
          <AddNodeBtn
            label={page_bot('flow_canvas_node_condition')}
            onClick={() => addNode('condition')}
            icon="◇"
            color="text-yellow-600"
          />
          <AddNodeBtn
            label={page_bot('flow_canvas_node_end')}
            onClick={() => addNode('end')}
            icon="■"
            color="text-red-600"
          />
        </div>

        {selectedEdgeId && (
          <div className="absolute top-14 right-4 z-10 rounded-md border bg-white/95 p-3 shadow-lg backdrop-blur supports-[backdrop-filter]:bg-white/80">
            <div className="text-muted-foreground mb-2 text-xs font-medium">
              {page_bot('flow_canvas_selected_connection')}
            </div>
            <div className="text-muted-foreground mb-3 font-mono text-[10px]">
              {selectedEdgeId}
            </div>
            <Button
              type="button"
              variant="destructive"
              size="sm"
              className="w-full"
              onClick={deleteSelectedEdge}
            >
              {page_bot('flow_canvas_delete_connection')}
            </Button>
          </div>
        )}

        {/* Right Properties Panel */}
        {selectedNode && (
          <div className="bg-card animate-in slide-in-from-right-4 absolute top-0 right-0 bottom-0 z-20 w-72 flex-shrink-0 overflow-y-auto border-l p-4 shadow-xl duration-200">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="truncate pr-2 text-sm font-medium">
                {(selectedNode.data as any).label || selectedNode.type}
              </h3>
              <button
                type="button"
                onClick={() => setSelectedNodeId(null)}
                className="text-muted-foreground hover:text-foreground text-xs"
              >
                ✕
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="text-muted-foreground mb-1 block text-xs font-medium">
                  {page_bot('flow_canvas_node_id')}
                </label>
                <div className="text-muted-foreground bg-muted inline-block rounded px-1 py-0.5 font-mono text-[10px]">
                  {selectedNode.id}
                </div>
              </div>

              <div>
                <label className="mb-1 block text-xs font-medium">
                  {page_bot('flow_canvas_label')}
                </label>
                <Input
                  value={(selectedNode.data as any).label || ''}
                  onChange={(e) =>
                    updateSelectedNodeData({ label: e.target.value })
                  }
                  className="h-8 text-sm"
                />
              </div>

              {selectedNode.type !== 'startEnd' && (
                <div>
                  <label className="mb-1 block text-xs font-medium">
                    {page_bot('flow_canvas_prompt')}
                  </label>
                  <Textarea
                    value={(selectedNode.data as any).prompt || ''}
                    onChange={(e) =>
                      updateSelectedNodeData({ prompt: e.target.value })
                    }
                    rows={6}
                    className="text-sm"
                    placeholder={
                      selectedNode.type === 'condition'
                        ? page_bot('flow_canvas_condition_prompt_placeholder')
                        : page_bot('flow_canvas_prompt_placeholder')
                    }
                  />
                </div>
              )}

              {mode === 'skill' &&
                selectedNode.type !== 'startEnd' &&
                selectedNode.data.type !== 'start' &&
                selectedNode.data.type !== 'end' && (
                  <div>
                    <label className="mb-1 block text-xs font-medium">
                      {page_bot('flow_configure_tools')}
                    </label>
                    <ToolConfigPopover
                      nodeId={selectedNodeId}
                      tools={skillTools}
                      currentValue={(selectedNode.data as any).tools || []}
                      onChange={(newTools: string[]) =>
                        updateSelectedNodeData({ tools: newTools })
                      }
                    />
                  </div>
                )}

              {mode === 'skill' && selectedNode.type === 'condition' && (
                <>
                  <div>
                    <label className="mb-1 block text-xs font-medium">
                      {page_bot('flow_canvas_condition_source_node')}
                    </label>
                    <Select
                      value={String(
                        (selectedNode.data as any).source_node_id || '',
                      )}
                      onValueChange={(value) =>
                        updateSelectedNodeData({ source_node_id: value })
                      }
                    >
                      <SelectTrigger className="h-8 text-sm">
                        <SelectValue
                          placeholder={page_bot(
                            'flow_canvas_condition_source_node_placeholder',
                          )}
                        />
                      </SelectTrigger>
                      <SelectContent>
                        {selectableActionNodes.map((node) => (
                          <SelectItem key={node.id} value={node.id}>
                            {String((node.data as any).label || node.id)}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div>
                    <label className="mb-1 block text-xs font-medium">
                      {page_bot('flow_canvas_condition_field')}
                    </label>
                    <Input
                      value={String((selectedNode.data as any).field || '')}
                      onChange={(e) =>
                        updateSelectedNodeData({ field: e.target.value })
                      }
                      className="h-8 text-sm"
                      placeholder={page_bot(
                        'flow_canvas_condition_field_placeholder',
                      )}
                    />
                  </div>

                  <div>
                    <label className="mb-1 block text-xs font-medium">
                      {page_bot('flow_canvas_condition_operator')}
                    </label>
                    <Select
                      value={String(
                        (selectedNode.data as any).operator || 'equals',
                      )}
                      onValueChange={(value) =>
                        updateSelectedNodeData({ operator: value })
                      }
                    >
                      <SelectTrigger className="h-8 text-sm">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="equals">
                          {page_bot('flow_canvas_condition_operator_equals')}
                        </SelectItem>
                        <SelectItem value="not_equals">
                          {page_bot(
                            'flow_canvas_condition_operator_not_equals',
                          )}
                        </SelectItem>
                        <SelectItem value="exists">
                          {page_bot('flow_canvas_condition_operator_exists')}
                        </SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  {String((selectedNode.data as any).operator || 'equals') !==
                    'exists' && (
                    <div>
                      <label className="mb-1 block text-xs font-medium">
                        {page_bot('flow_canvas_condition_expected_value')}
                      </label>
                      <Input
                        value={String(
                          (selectedNode.data as any).expected_value || '',
                        )}
                        onChange={(e) =>
                          updateSelectedNodeData({
                            expected_value: e.target.value,
                          })
                        }
                        className="h-8 text-sm"
                        placeholder={page_bot(
                          'flow_canvas_condition_expected_value_placeholder',
                        )}
                      />
                    </div>
                  )}
                </>
              )}

              {mode === 'intent-router' &&
                selectedNode.type !== 'startEnd' &&
                selectedNode.type === 'action' && (
                  <div>
                    <label className="mb-1 block text-xs font-medium">
                      {page_bot('target_skill')}
                    </label>
                    <Select
                      value={String(
                        (selectedNode.data as any).target_skill_id || '',
                      )}
                      onValueChange={(value) =>
                        updateSelectedNodeData({ target_skill_id: value })
                      }
                    >
                      <SelectTrigger className="h-8 text-sm">
                        <SelectValue placeholder={page_bot('target_skill')} />
                      </SelectTrigger>
                      <SelectContent>
                        {(skillOptions || []).map((skill) => (
                          <SelectItem key={skill.id} value={skill.id}>
                            {skill.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                )}

              {mode === 'intent-router' && selectedNode.type !== 'startEnd' && (
                <div>
                  <label className="mb-1 block text-xs font-medium">
                    {page_bot('intent_router_examples')}
                  </label>
                  <Textarea
                    value={(selectedNode.data as any).examples_text || ''}
                    onChange={(e) =>
                      updateSelectedNodeData({ examples_text: e.target.value })
                    }
                    rows={4}
                    className="text-sm"
                    placeholder={page_bot('intent_router_examples_placeholder')}
                  />
                </div>
              )}

              {selectedNode.type !== 'startEnd' && (
                <div>
                  <label className="mb-1 block text-xs font-medium">
                    {page_bot('flow_canvas_note')}
                  </label>
                  <Textarea
                    value={(selectedNode.data as any).note || ''}
                    onChange={(e) =>
                      updateSelectedNodeData({ note: e.target.value })
                    }
                    rows={3}
                    className="text-sm"
                  />
                </div>
              )}

              <div className="border-t pt-2">
                <Button
                  type="button"
                  variant="destructive"
                  size="sm"
                  className="w-full"
                  onClick={deleteSelectedNode}
                >
                  {page_bot('flow_canvas_delete_node')}
                </Button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

// --- Subcomponents ---

const AddNodeBtn = ({ label, onClick, icon, color }: any) => (
  <Button
    type="button"
    size="icon"
    variant="ghost"
    onClick={onClick}
    className={`hover:bg-muted h-8 w-8 rounded-sm ${color} hover:text-foreground`}
    title={label}
  >
    <span className="text-sm">{icon}</span>
  </Button>
);

// Re-implement Popover
const ToolConfigPopover = ({ nodeId, tools, currentValue, onChange }: any) => {
  const page_bot = useTranslations('page_bot');

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          className="h-8 w-full justify-between text-xs"
        >
          <span>{page_bot('flow_configure_tools')}</span>
          <svg
            className="ml-1 h-3 w-3 opacity-50"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <path d="M6 9l6 6 6-6" />
          </svg>
        </Button>
      </PopoverTrigger>
      <PopoverContent className="z-50 w-64 p-0">
        <div className="p-2">
          <div className="text-muted-foreground mb-1 px-1 py-1 text-[10px] font-bold tracking-wider uppercase">
            {page_bot('flow_canvas_available_tools')}
          </div>
          {tools.length === 0 ? (
            <p className="text-muted-foreground p-2 text-xs">
              {page_bot('flow_canvas_no_tools')}
            </p>
          ) : (
            <div className="space-y-0.5">
              {tools.map((t: any) => {
                const isChecked = currentValue.includes(t.id);
                return (
                  <label
                    key={t.id}
                    className="hover:bg-accent flex cursor-pointer items-start gap-2 rounded-md p-1.5 text-xs"
                  >
                    <Checkbox
                      checked={isChecked}
                      onCheckedChange={() => {
                        onChange(
                          isChecked
                            ? currentValue.filter((x: string) => x !== t.id)
                            : [...currentValue, t.id],
                        );
                      }}
                    />
                    <div className="min-w-0 flex-1">
                      <div className="font-medium break-all">{t.name}</div>
                      {t.description ? (
                        <div className="text-muted-foreground mt-0.5 text-[11px] leading-4">
                          {t.description}
                        </div>
                      ) : null}
                    </div>
                  </label>
                );
              })}
            </div>
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
};

// --- Node Rendering ---

const StartEndNode = ({ data, selected }: any) => (
  <div
    className={`rounded-full border-2 px-6 py-2 shadow-sm transition-all ${selected ? 'border-blue-500 ring-2 ring-blue-500/20' : 'border-green-500'} bg-white`}
  >
    <div className="text-center text-xs font-bold whitespace-nowrap text-green-700">
      {data.label}
    </div>
    <Handle
      type="source"
      position={Position.Right}
      id="right"
      className="!h-2.5 !w-2.5 !bg-green-600"
    />
    <Handle
      type="target"
      position={Position.Left}
      id="left"
      className="!h-2.5 !w-2.5 !bg-green-600"
    />
  </div>
);

const ActionNode = ({ data, selected }: any) => (
  <div
    className={`w-40 rounded-lg border-2 bg-white px-4 py-3 shadow-sm transition-all ${selected ? 'border-blue-500 ring-2 ring-blue-500/20' : 'border-slate-200 hover:border-slate-300'}`}
  >
    <div className="mb-1 flex items-center gap-2">
      <div className="flex size-5 items-center justify-center rounded bg-blue-100 text-sm">
        ⚡
      </div>
      <div className="flex-1 truncate text-xs font-bold">{data.label}</div>
    </div>
    {data.tools?.length > 0 && (
      <div className="mt-2 flex flex-wrap gap-1">
        {data.tools.map((t: string) => (
          <span
            key={t}
            className="bg-accent text-accent-foreground rounded-sm border px-1.5 py-0.5 text-[10px]"
          >
            {t}
          </span>
        ))}
      </div>
    )}

    <Handle
      type="target"
      position={Position.Top}
      className="!h-2.5 !w-2.5 !bg-slate-400"
    />
    <Handle
      type="source"
      position={Position.Bottom}
      className="!h-2.5 !w-2.5 !bg-slate-400"
    />
  </div>
);

const ConditionNode = ({ data, selected }: any) => (
  <div className="group relative flex size-32 items-center justify-center">
    <div
      className={`absolute inset-5 rotate-45 transform rounded border-2 shadow-sm transition-all ${selected ? 'border-yellow-500 ring-2 ring-blue-500/20' : 'border-yellow-400 group-hover:border-yellow-500'} bg-white`}
    />

    <div className="pointer-events-none relative z-10 text-center whitespace-nowrap">
      <div className="text-[10px] font-bold text-yellow-700">{data.label}</div>
    </div>

    <Handle
      type="target"
      position={Position.Top}
      className="!h-2.5 !w-2.5 !bg-yellow-500"
    />
    <Handle
      type="source"
      id="yes"
      position={Position.Right}
      className="!h-2.5 !w-2.5 !bg-green-500"
    />
    <Handle
      type="source"
      id="no"
      position={Position.Bottom}
      className="!h-2.5 !w-2.5 !bg-red-500"
    />
  </div>
);
