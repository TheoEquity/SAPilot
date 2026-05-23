'use client';

import React, { useCallback, useEffect, useState, useRef, useMemo } from 'react';
import type { ReactFlowInstance, Node, Edge, NodeTypes, NodeProps, Connection } from 'reactflow';
import ReactFlow, { 
  Background, 
  Controls, 
  MarkerType, 
  Handle, 
  Position,
  addEdge,
} from 'reactflow';
import 'reactflow/dist/style.css';

import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { useTranslations } from 'next-intl';
import { DialogTitle } from '@/components/ui/dialog';
import type { ReactFlowSchema, ReactFlowNode, ReactFlowEdge } from './orchestration-types';

export const FlowCanvasEditor = ({
  value,
  onChange,
  skillTools = [],
}: {
  value: ReactFlowSchema;
  onChange: (value: ReactFlowSchema) => void;
  skillTools?: Array<{ id: string; name: string; description?: string }>;
}) => {
  const page_bot = useTranslations('page_bot');
  
  // Internal State
  const [nodes, setNodes] = useState<Node[]>(value.nodes || []);
  const [edges, setEdges] = useState<Edge[]>(value.edges || []);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedNodeData, setSelectedNodeData] = useState<Record<string, any> | null>(null);
  const [reactFlowInstance, setReactFlowInstance] = useState<ReactFlowInstance | null>(null);

  // Sync from parent
  useEffect(() => {
    if (value) {
      setNodes(value.nodes || []);
      setEdges(value.edges || []);
      // Try to restore selected node
      if (value.nodes?.length > 0 && selectedNodeId) {
        const exists = value.nodes.find(n => n.id === selectedNodeId);
        if (exists) {
          setSelectedNodeData(exists.data);
        }
      } else {
         // Deselect if node is gone
         if (selectedNodeId) {
            const found = value.nodes.find(n => n.id === selectedNodeId);
            if (!found) { setSelectedNodeId(null); setSelectedNodeData(null); }
         }
      }
    }
  }, [value, nodes, selectedNodeId]);

  // Sync to parent
  const syncChanges = useCallback((currentNodes: Node[], currentEdges: Edge[]) => {
    onChange({
        version: value.version || "v2",
        nodes: currentNodes.map(n => ({
            id: n.id,
            type: n.type || 'action',
            position: n.position,
            data: n.data
        })) as ReactFlowNode[],
        edges: currentEdges.map(e => ({
            id: e.id,
            source: e.source,
            target: e.target,
            sourceHandle: e.sourceHandle,
            targetHandle: e.targetHandle,
            data: e.data
        })) as ReactFlowEdge[],
    });
  }, [onChange, value.version]);

  // Node Types
  const nodeTypes: NodeTypes = useMemo(() => ({
    startEnd: StartEndNode,
    action: ActionNode,
    condition: ConditionNode,
  }), []);

  const onNodesChange = useCallback((changes: any) => {
    const newNodes = nodes.map((node) => {
        const change = changes.find((c: any) => c.id === node.id);
        if (change) {
            if (change.type === 'position') {
                return { ...node, position: change.position };
            }
        }
        return node;
    });
    setNodes(newNodes);
    syncChanges(newNodes, edges);
  }, [nodes, edges, syncChanges]);

  const onEdgesChange = useCallback((changes: any) => {
    // Remove edges if deleted
    const remainingIds = edges.map(e => e.id).filter(id => !changes.some((c: any) => c.id === id && c.type === 'remove'));
    const newEdges = edges.filter(e => remainingIds.includes(e.id));
    setEdges(newEdges);
    syncChanges(nodes, newEdges);
  }, [edges, nodes, syncChanges]);

  const onConnect = useCallback((params: any) => {
    const newEdge = {
        ...params,
        id: `e-${params.source}-${params.target}`,
        markerEnd: { type: MarkerType.ArrowClosed, width: 15, height: 15 },
        style: { strokeWidth: 1.5 },
    };
    const newEdges = addEdge(newEdge, edges);
    setEdges(newEdges);
    syncChanges(nodes, newEdges);
  }, [edges, nodes, syncChanges]);

  const onNodeClick = useCallback((_: any, node: Node) => {
    setSelectedNodeId(node.id);
    setSelectedNodeData({ ...node.data });
  }, []);

  const updateSelectedNode = useCallback((updates: Record<string, any>) => {
    if (!selectedNodeId) return;

    const newNodes = nodes.map(n => 
        n.id === selectedNodeId 
        ? { ...n, data: { ...n.data, ...updates } } 
        : n
    );
    setNodes(newNodes);
    setSelectedNodeData(prev => ({ ...prev, ...updates }));
    syncChanges(newNodes, edges);
  }, [selectedNodeId, nodes, edges, syncChanges]);

  // Add Node Handlers
  const addNode = useCallback((type: 'start' | 'action' | 'condition' | 'end') => {
      const id = `${type}-${Date.now()}`;
      let data: any = { label: type.charAt(0).toUpperCase() + type.slice(1) };
      if (type === 'action') data = { ...data, label: 'LLM Action', tools: [] };
      if (type === 'condition') data = { ...data, label: 'Condition' };
      
      const newNodeType = (type === 'start' || type === 'end') ? 'startEnd' : type === 'condition' ? 'condition' : 'action';
      
      const newNode = {
          id,
          type: newNodeType,
          position: { x: Math.random() * 300, y: Math.random() * 300 }, // Random pos for now, layout later
          data
      };
      
      const newNodes = [...nodes, newNode];
      setNodes(newNodes);
      syncChanges(newNodes, edges);
  }, [nodes, edges, syncChanges]);

  return (
    <div className="flex h-[600px] w-full overflow-hidden rounded-lg border">
        {/* Left Canvas */}
        <div className="flex-1 border-r bg-muted/10 relative">
            <ReactFlow
                nodes={nodes}
                edges={edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onConnect={onConnect}
                onNodeClick={onNodeClick}
                nodeTypes={nodeTypes}
                fitView
            >
                <Background />
                <Controls />
            </ReactFlow>

            {/* Floating Add Menu */}
            <div className="absolute left-4 top-4 z-10 flex gap-2 rounded-lg border bg-card p-1 shadow-sm">
                <AddNodeBtn label="Start" onClick={() => addNode('start')} icon="▶" color="bg-green-100 text-green-700" />
                <AddNodeBtn label="Action" onClick={() => addNode('action')} icon="☕" color="bg-blue-100 text-blue-700" />
                <AddNodeBtn label="Condition" onClick={() => addNode('condition')} icon="◇" color="bg-yellow-100 text-yellow-700" />
                <AddNodeBtn label="End" onClick={() => addNode('end')} icon="■" color="bg-red-100 text-red-700" />
            </div>
            
             {/* Empty Hint */}
            {nodes.length === 0 && (
                <div className="absolute inset-0 flex items-center justify-center pointer-events-none select-none">
                    <span className="text-muted-foreground text-sm">Click + to add node</span>
                </div>
            )}
        </div>

        {/* Right Properties Panel */}
        {selectedNodeId && selectedNodeData && (
            <div className="w-72 flex-shrink-0 bg-card p-4 shadow-lg">
                <h3 className="mb-4 font-medium text-sm text-muted-foreground">Node: {selectedNodeData.label}</h3>
                
                <label className="mb-2 block text-xs font-medium">Label</label>
                <Input 
                    value={selectedNodeData.label || ''} 
                    onChange={e => updateSelectedNode({ label: e.target.value })}
                    className="mb-4"
                />

                {selectedNodeData.type !== 'start' && selectedNodeData.type !== 'end' && (
                    <>
                        <label className="mb-2 block text-xs font-medium">{page_bot('flow_configure_tools')}</label>
                        <ToolConfigPopover 
                            toolId={selectedNodeId} 
                            tools={skillTools} 
                            currentValue={selectedNodeData.tools || []} 
                            onChange={(newTools: string[]) => updateSelectedNode({ tools: newTools })} 
                        />
                    </>
                )}
                
                <label className="mb-2 mt-4 block text-xs font-medium">Note</label>
                <Textarea 
                    value={selectedNodeData.note || ''} 
                    onChange={e => updateSelectedNode({ note: e.target.value })}
                    rows={3}
                />
            </div>
        )}
    </div>
  );
}

// --- Components ---

const AddNodeBtn = ({ label, onClick, icon, color }: any) => (
    <Button size="sm" variant="ghost" onClick={onClick} className={`h-8 px-2 flex items-center gap-1 ${color}`}>
        {icon} <span className="text-[10px]">{label}</span>
    </Button>
);

const ToolConfigPopover = ({ toolId, tools, currentValue, onChange }: any) => {
    const page_bot = useTranslations('page_bot');
    
    return (
        <Popover>
            <PopoverTrigger asChild>
                 <Button variant="outline" size="sm" className="w-full mb-4 justify-between">
                    <span>Configure Tools</span>
                    <svg className="ml-2 h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M6 9l6 6 6-6"/></svg>
                 </Button>
            </PopoverTrigger>
            <PopoverContent className="w-64 p-2">
                {tools.length === 0 ? <p className="text-xs text-muted-foreground">No tools available.</p> : (
                    tools.map((t: any) => {
                        const isChecked = currentValue.includes(t.id);
                        return (
                            <div key={t.id} className="flex items-center gap-2 mb-1 rounded-sm p-1 hover:bg-accent">
                                <Checkbox checked={isChecked} onCheckedChange={() => {
                                    onChange(isChecked ? currentValue.filter((x: string) => x !== t.id) : [...currentValue, t.id]);
                                }}/>
                                <span className="text-xs">{t.name}</span>
                            </div>
                        )
                    })
                )}
            </PopoverContent>
        </Popover>
    );
};

// --- Custom Nodes ---

const StartEndNode = ({ data, selected }: NodeProps) => (
    <div className={`rounded-full border-2 px-4 py-2 ${selected ? 'border-blue-500 shadow-md' : 'border-green-500 bg-green-50'}`}>
        <div className="text-center text-xs font-bold text-green-700 whitespace-nowrap">{data.label}</div>
        <Handle type="target" position={Position.Left} isConnectable={false} className="!bg-green-800 !w-2 !h-2" />
        <Handle type="source" position={Position.Right} className="!bg-green-800 !w-2 !h-2" />
    </div>
);

const ConditionNode = ({ data, selected }: NodeProps) => (
    <div className="relative w-24 h-24 flex items-center justify-center">
        {/* Diamond Shape */}
        <div className={`absolute inset-0 transform rotate-45 border-2 ${selected ? 'border-blue-500 shadow-md' : 'border-yellow-400 bg-yellow-50'}`} />
        
        <div className="relative z-10 text-center whitespace-nowrap pointer-events-none">
            <div className="text-[10px] font-bold text-yellow-700">{data.label}</div>
            {data.condition && <div className="text-[8px] text-yellow-600">{data.condition}</div>}
        </div>

        <Handle type="target" position={Position.Top} className="!bg-yellow-800 !w-2 !h-2" />
        <Handle type="source" id="yes" position={Position.Right} className="!bg-green-500 !w-2 !h-2" />
        <Handle type="source" id="no" position={Position.Bottom} className="!bg-red-500 !w-2 !h-2" />
    </div>
);

const ActionNode = ({ data, selected }: NodeProps) => (
    <div className={`group rounded-lg border-2 px-3 py-2 shadow-sm bg-card transition-colors ${selected ? 'border-blue-500' : 'border-border'}`}>
        <div className="mb-1 flex items-center gap-2">
            <div className="flex size-4 items-center justify-center rounded bg-blue-100 text-xs">☕</div>
            <div className="text-xs font-bold truncate max-w-[80px]">{data.label}</div>
        </div>
        <div className="text-[9px] text-muted-foreground truncate max-w-[100px]">
            {data.tools?.length > 0 ? `Enabled: ${data.tools.length}` : 'No tools configured'}
        </div>
        
        <Handle type="target" position={Position.Top} className="!bg-zinc-400 !w-2 !h-2" />
        <Handle type="source" position={Position.Bottom} className="!bg-zinc-400 !w-2 !h-2" />
    </div>
);