import React from 'react';
import { ReactFlow, Controls } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { getLayoutedGraph } from '@/components/Graph/Layout';
import { FileAnalysis } from '@/types/file_analysis_type';
import { ComplexityLegend } from '@/components/ComplexityLegend';


function CallGraph({analysis}:{analysis:FileAnalysis}) {
    
    if (!analysis) return <div>Loading graph...</div>;
    console.log(analysis)

  const { nodes, edges } = getLayoutedGraph(
    analysis.call_graph.nodes,
    analysis.call_graph.edges,
    'TB'
  );

  const proOptions = { hideAttribution: true };

  return (
    <div style={{ height: '100%', width: '100%' }}>
      <ComplexityLegend />
      <ReactFlow
        defaultNodes={nodes}
        defaultEdges={edges}
        fitView
        proOptions={proOptions}
        nodesDraggable
        nodesConnectable={false} 

      >
        <Controls />
      </ReactFlow>
    </div>
  );
}

export default CallGraph;
