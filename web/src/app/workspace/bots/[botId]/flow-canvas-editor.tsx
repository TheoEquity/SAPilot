'use client';

import React, { useCallback, useState, useRef, useMemo, useEffect } from 'react';
import type { Node, Edge, NodeTypes, NodeChange, EdgeChange, Connection } from 'reactflow';
import ReactFlow, { 
  Background, 
  Controls,
  Handle, 
  Position,
  addEdge,
  applyNodeChanges,
  applyEdgeChanges,
  MarkerType,
} from 'reactflow';
import 'reactflow/dist/style.css';

import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { useTranslations } from 'next-intl';
import { toast } from 'sonner';
import type { ReactFlowEdge, ReactFlowSchema } from './orchestration-types';

export const FlowCanvasEditor = ({
  title, description,
  value,
  onChange,
  skillOptions,
  skillTools = [],
  onQuickSave,
}: {
  title: string;
  description: string;
  value: ReactFlowSchema;
  onChange: (value: ReactFlowSchema) => void;
  skillOptions?: Array<{ id: string; label: string }>;
  skillTools?: Array<{ id: string; name: string; description?: string }>;
  onQuickSave?: (value: ReactFlowSchema) => Promise<boolean>;
}) => {
  const [nodes, setNodes] = useState<Node[]>(value?.nodes || []);
  const [edges, setEdges] = useState<Edge[]>(value?.edges || []);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);
  const [saveState, setSaveState] = useState<'idle' | 'saving' | 'saved'>('idle');
  const isSavingRef = useRef(false);
  const reactFlowWrapper = useRef<HTMLDivElement>(null);
  
  const page_bot = useTranslations('page_bot');

  useEffect(() => {
    if (value?.nodes?.length !== nodes.length || value?.edges?.length !== edges.length) {
       setNodes(value.nodes || []);
       setEdges(value.edges || []);
    }
  }, [value]);

  const onNodesChange = useCallback(
    (changes: NodeChange[]) => {
      setNodes((nds) => applyNodeChanges(changes, nds));
      setSaveState('idle');
    },
    []
  );

  const onEdgesChange = useCallback(
    (changes: EdgeChange[]) => {
      setEdges((eds) => applyEdgeChanges(changes, eds));
      setSaveState('idle');
    },
    []
  );

  const onConnect = useCallback(
    (connection: Connection) => {
      const newEdge = {
          ...connection,
          id: `e-${connection.source}-${connection.target}`,
          markerEnd: { type: MarkerType.ArrowClosed, width: 15, height: 15, color: '#94a3b8' },
          style: { strokeWidth: 2 },
      };
      setEdges((eds) => addEdge(newEdge, eds));
      setSaveState('idle');
    },
    []
  );

  const saveToParent = useRef(
    setTimeout(() => {}, 0)
  );

  const buildSchema = useCallback((currNodes: Node[], currEdges: Edge[]): ReactFlowSchema => ({
    version: value?.version || 'v2',
    nodes: currNodes.map((n) => ({
      id: n.id,
      type: n.type || 'action',
      position: n.position,
      data: n.data,
    })),
    edges: currEdges.map((e): ReactFlowEdge => ({
      id: e.id,
      source: e.source,
      target: e.target,
      sourceHandle: e.sourceHandle ?? undefined,
      targetHandle: e.targetHandle ?? undefined,
      data: e.data,
    })),
  }), [value?.version]);

  const syncChanges = useCallback((currNodes: Node[], currEdges: Edge[]) => {
    clearTimeout(saveToParent.current);
    saveToParent.current = setTimeout(() => {
      onChange(buildSchema(currNodes, currEdges));
    }, 300);
  }, [buildSchema, onChange]);

  const saveNow = useCallback(async () => {
    if (isSavingRef.current) return;
    isSavingRef.current = true;
    setSaveState('saving');
    try {
      const nextFlow = buildSchema(nodes, edges);
      clearTimeout(saveToParent.current);
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
    return () => { isMounted.current = false; clearTimeout(saveToParent.current); };
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
      setNodes((prev) => prev.filter(n => n.id !== selectedNodeId));
      setEdges((prev) => prev.filter(e => e.source !== selectedNodeId && e.target !== selectedNodeId));
      setSelectedNodeId(null);
      setSaveState('idle');
  }, [selectedNodeId]);

  const deleteSelectedEdge = useCallback(() => {
      if (!selectedEdgeId) return;
      setEdges((prev) => prev.filter((edge) => edge.id !== selectedEdgeId));
      setSelectedEdgeId(null);
      setSaveState('idle');
  }, [selectedEdgeId]);

  const addNode = useCallback((type: 'start' | 'action' | 'condition' | 'end') => {
      let position = { x: 250, y: 250 };
      
      const id = `${type}-${Date.now()}`;
      let data: any = { label: type.charAt(0).toUpperCase() + type.slice(1) };
      if (type === 'action') data = { ...data, label: page_bot('flow_canvas_default_action_label'), tools: [] };
      if (type === 'condition') data = { ...data, label: page_bot('flow_canvas_default_condition_label') };
      
      const newNodeTypeMap: Record<string, string> = {
          'start': 'startEnd',
          'end': 'startEnd',
          'action': 'action',
          'condition': 'condition'
      };

      const newNode = {
          id,
          type: newNodeTypeMap[type],
          position,
          data
      };
      
      setNodes((prev) => [...prev, newNode]);
      setSaveState('idle');
  }, [page_bot]);

  const updateSelectedNodeData = useCallback((updates: Record<string, any>) => {
      setNodes((nds) => nds.map((node) => {
          if (node.id === selectedNodeId) {
              return { ...node, data: { ...node.data, ...updates } };
          }
          return node;
      }));
      setSaveState('idle');
  }, [selectedNodeId]);

  const nodeTypes: NodeTypes = useMemo(() => ({
    startEnd: StartEndNode,
    action: ActionNode,
    condition: ConditionNode,
  }), []);

  const selectedNode = nodes.find(n => n.id === selectedNodeId);

  return (
    <div className="flex h-[600px] w-full flex-col overflow-hidden rounded-lg border bg-muted/5" ref={reactFlowWrapper}>
        <div className="flex h-10 shrink-0 items-center justify-between border-b bg-card px-4">
             <div className="flex items-center">
                <span className="text-sm font-medium">{title}</span>
                <span className="ml-2 text-xs text-muted-foreground">{description}</span>
             </div>
             <div className="flex items-center gap-2">
                 {saveState === 'saved' ? (
                     <span className="text-xs text-green-600 animate-pulse">{page_bot('flow_canvas_saved_badge')}</span>
                 ) : (
                      <span className="text-xs text-muted-foreground">{page_bot('flow_canvas_counts', { nodes: String(nodes.length), edges: String(edges.length) })}</span>
                )}
                <Button
                    type="button"
                    size="sm"
                    onClick={saveNow}
                    disabled={saveState === 'saving'}
                    className={`${saveState === 'saved' ? 'bg-green-600 text-white' : ''}`}
                >
                    {saveState === 'saving' ? page_bot('flow_canvas_saving') : saveState === 'saved' ? page_bot('flow_canvas_saved_short') : page_bot('save_bot')}
                </Button>
             </div>
        </div>
        
        <div className="relative flex-1 w-full overflow-hidden" style={{ width: '100%', height: '100%' }}>
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
            <div className="absolute left-4 top-4 z-10 flex gap-1 rounded-md border bg-white/90 p-1 shadow-lg backdrop-blur supports-[backdrop-filter]:bg-white/60">
                <AddNodeBtn label={page_bot('flow_canvas_node_start')} onClick={() => addNode('start')} icon="▶" color="text-green-600" />
                <AddNodeBtn label={page_bot('flow_canvas_node_action')} onClick={() => addNode('action')} icon="⚡" color="text-blue-600" />
                <AddNodeBtn label={page_bot('flow_canvas_node_condition')} onClick={() => addNode('condition')} icon="◇" color="text-yellow-600" />
                <AddNodeBtn label={page_bot('flow_canvas_node_end')} onClick={() => addNode('end')} icon="■" color="text-red-600" />
            </div>

            {selectedEdgeId && (
                <div className="absolute right-4 top-14 z-10 rounded-md border bg-white/95 p-3 shadow-lg backdrop-blur supports-[backdrop-filter]:bg-white/80">
                    <div className="mb-2 text-xs font-medium text-muted-foreground">{page_bot('flow_canvas_selected_connection')}</div>
                    <div className="mb-3 font-mono text-[10px] text-muted-foreground">{selectedEdgeId}</div>
                    <Button type="button" variant="destructive" size="sm" className="w-full" onClick={deleteSelectedEdge}>
                        {page_bot('flow_canvas_delete_connection')}
                    </Button>
                </div>
            )}

            {/* Right Properties Panel */}
            {selectedNode && (
                <div className="absolute right-0 top-0 bottom-0 w-72 flex-shrink-0 border-l bg-card shadow-xl z-20 overflow-y-auto p-4 animate-in slide-in-from-right-4 duration-200">
                    <div className="mb-4 flex items-center justify-between">
                        <h3 className="font-medium text-sm truncate pr-2">{(selectedNode.data as any).label || selectedNode.type}</h3>
                        <button type="button" onClick={() => setSelectedNodeId(null)} className="text-xs text-muted-foreground hover:text-foreground">✕</button>
                    </div>
                    
                    <div className="space-y-4">
                        <div>
                            <label className="mb-1 block text-xs font-medium text-muted-foreground">{page_bot('flow_canvas_node_id')}</label>
                            <div className="font-mono text-[10px] text-muted-foreground bg-muted px-1 py-0.5 rounded inline-block">{selectedNode.id}</div>
                        </div>

                        <div>
                            <label className="mb-1 block text-xs font-medium">{page_bot('flow_canvas_label')}</label>
                            <Input 
                                value={(selectedNode.data as any).label || ''} 
                                onChange={e => updateSelectedNodeData({ label: e.target.value })}
                                className="h-8 text-sm"
                            />
                        </div>

                        {(selectedNode.type !== 'startEnd' && selectedNode.data.type !== 'start' && selectedNode.data.type !== 'end') && (
                            <div>
                                <label className="mb-1 block text-xs font-medium">{page_bot('flow_configure_tools')}</label>
                                <ToolConfigPopover 
                                    nodeId={selectedNodeId} 
                                    tools={skillTools} 
                                    currentValue={(selectedNode.data as any).tools || []} 
                                    onChange={(newTools: string[]) => updateSelectedNodeData({ tools: newTools })} 
                                />
                            </div>
                        )}
                        
                        {selectedNode.type !== 'startEnd' && (
                            <div>
                                <label className="mb-1 block text-xs font-medium">{page_bot('flow_canvas_note')}</label>
                                <Textarea 
                                    value={(selectedNode.data as any).note || ''} 
                                    onChange={e => updateSelectedNodeData({ note: e.target.value })}
                                    rows={3}
                                    className="text-sm"
                                />
                            </div>
                        )}

                        <div className="pt-2 border-t">
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
}

// --- Subcomponents ---

const AddNodeBtn = ({ label, onClick, icon, color }: any) => (
    <Button type="button" size="icon" variant="ghost" onClick={onClick} className={`h-8 w-8 rounded-sm hover:bg-muted ${color} hover:text-foreground`} title={label}>
        <span className="text-sm">{icon}</span>
    </Button>
);

// Re-implement Popover
const ToolConfigPopover = ({ nodeId, tools, currentValue, onChange }: any) => {
    const page_bot = useTranslations('page_bot');
    
    return (
        <Popover>
            <PopoverTrigger asChild>
                 <Button variant="outline" size="sm" className="w-full justify-between text-xs h-8">
                     <span>{page_bot('flow_configure_tools')}</span>
                    <svg className="ml-1 h-3 w-3 opacity-50" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M6 9l6 6 6-6"/></svg>
                 </Button>
            </PopoverTrigger>
            <PopoverContent className="w-64 p-0 z-50">
                <div className="p-2">
                     <div className="mb-1 px-1 py-1 text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
                       {page_bot('flow_canvas_available_tools')}
                     </div>
                    {tools.length === 0 ? <p className="p-2 text-xs text-muted-foreground">{page_bot('flow_canvas_no_tools')}</p> : (
                        <div className="space-y-0.5">
                            {tools.map((t: any) => {
                                const isChecked = currentValue.includes(t.id);
                                return (
                                    <label key={t.id} className="flex cursor-pointer items-center gap-2 rounded-md p-1.5 hover:bg-accent text-xs">
                                        <Checkbox checked={isChecked} onCheckedChange={() => {
                                            onChange(isChecked ? currentValue.filter((x: string) => x !== t.id) : [...currentValue, t.id]);
                                        }} />
                                        <span className="font-medium">{t.name}</span>
                                    </label>
                                )
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
    <div className={`rounded-full border-2 px-6 py-2 shadow-sm transition-all ${selected ? 'border-blue-500 ring-2 ring-blue-500/20' : 'border-green-500'} bg-white`}>
        <div className="text-center text-xs font-bold text-green-700 whitespace-nowrap">{data.label}</div>
        <Handle type="source" position={Position.Right} id="right" className="!bg-green-600 !w-2.5 !h-2.5" />
        <Handle type="target" position={Position.Left} id="left" className="!bg-green-600 !w-2.5 !h-2.5" />
    </div>
);

const ActionNode = ({ data, selected }: any) => (
    <div className={`rounded-lg border-2 px-4 py-3 shadow-sm bg-white w-40 transition-all ${selected ? 'border-blue-500 ring-2 ring-blue-500/20' : 'border-slate-200 hover:border-slate-300'}`}>
        <div className="mb-1 flex items-center gap-2">
            <div className="flex size-5 items-center justify-center rounded bg-blue-100 text-sm">⚡</div>
            <div className="text-xs font-bold truncate flex-1">{data.label}</div>
        </div>
        {(data.tools?.length > 0) && (
             <div className="mt-2 flex flex-wrap gap-1">
                {data.tools.map((t: string) => (
                    <span key={t} className="px-1.5 py-0.5 rounded-sm bg-accent text-[10px] border text-accent-foreground">{t}</span>
                ))}
             </div>
        )}
        
        <Handle type="target" position={Position.Top} className="!bg-slate-400 !w-2.5 !h-2.5" />
        <Handle type="source" position={Position.Bottom} className="!bg-slate-400 !w-2.5 !h-2.5" />
    </div>
);

const ConditionNode = ({ data, selected }: any) => (
    <div className="flex size-32 items-center justify-center relative group">
        <div className={`absolute inset-5 transform rotate-45 border-2 rounded shadow-sm transition-all ${selected ? 'border-yellow-500 ring-2 ring-blue-500/20' : 'border-yellow-400 group-hover:border-yellow-500'} bg-white`} />
        
        <div className="relative z-10 text-center whitespace-nowrap pointer-events-none">
            <div className="text-[10px] font-bold text-yellow-700">{data.label}</div>
        </div>

        <Handle type="target" position={Position.Top} className="!bg-yellow-500 !w-2.5 !h-2.5" />
        <Handle type="source" id="yes" position={Position.Right} className="!bg-green-500 !w-2.5 !h-2.5" />
        <Handle type="source" id="no" position={Position.Bottom} className="!bg-red-500 !w-2.5 !h-2.5" />
    </div>
);
