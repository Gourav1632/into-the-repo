import dagre from 'dagre';
import { Node, Edge, Position } from '@xyflow/react';
import { getComplexityColor, getComplexityBgColor, getComplexityBorderColor } from '@/lib/complexityColors';

const dagreGraph = new dagre.graphlib.Graph();
dagreGraph.setDefaultEdgeLabel(() => ({}));

const nodeWidth = 180;
const nodeHeight = 60;

export function getLayoutedGraph(
  nodes: Node[],
  edges: Edge[],
  direction: 'TB' | 'LR' = 'TB'
): { nodes: Node[]; edges: Edge[] } {
  dagreGraph.setGraph({ rankdir: direction });

  nodes.forEach((node) => {
    dagreGraph.setNode(node.id, { width: nodeWidth, height: nodeHeight });
  });

  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target);
  });

  dagre.layout(dagreGraph);

  const layoutedNodes = nodes.map((node) => {
    const pos = dagreGraph.node(node.id);
    const targetPosition: Position = direction === 'LR' ? Position.Left : Position.Top;
    const sourcePosition: Position = direction === 'LR' ? Position.Right : Position.Bottom;
    
    // Apply complexity-based styling
    const complexity = node.data?.complexity;
    const borderColor = getComplexityBorderColor(complexity);
    const bgColor = getComplexityBgColor(complexity);
    
    return {
      ...node,
      position: { x: pos.x - nodeWidth / 2, y: pos.y - nodeHeight / 2 },
      targetPosition,
      sourcePosition,
      style: {
        ...(node.style || {}),
        border: `2px solid ${borderColor}`,
        backgroundColor: bgColor,
        borderRadius: '8px',
        padding: '8px',
        fontSize: '12px',
        fontWeight: '500',
        boxShadow: `0 2px 8px ${borderColor}40`,
      },
    };
  });

  return { nodes: layoutedNodes, edges };
}
