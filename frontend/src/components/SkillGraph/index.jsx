import React, { useCallback, useMemo } from 'react';
import { ReactFlow, Background, Controls, MiniMap, MarkerType } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import SkillNode from './SkillNode';
import '../../styles/components/skill-graph.css';

const nodeTypes = { skillNode: SkillNode };

function computeLevels(nodes, edges, importance = {}) {
  const graph = new Map();
  const inDegree = new Map();
  nodes.forEach(node => {
    graph.set(node.id, []);
    inDegree.set(node.id, 0);
  });
  edges.forEach(edge => {
    graph.get(edge.source).push(edge.target);
    inDegree.set(edge.target, inDegree.get(edge.target) + 1);
  });

  const queue = [];
  for (let [nodeId, degree] of inDegree.entries()) {
    if (degree === 0) queue.push(nodeId);
  }
  queue.sort((a, b) => (importance[b] || 0) - (importance[a] || 0));

  const levels = new Map();
  let currentLevel = 0;

  while (queue.length) {
    const levelSize = queue.length;
    for (let i = 0; i < levelSize; i++) {
      const nodeId = queue.shift();
      levels.set(nodeId, currentLevel);
      for (const neighbor of graph.get(nodeId)) {
        const newDegree = inDegree.get(neighbor) - 1;
        inDegree.set(neighbor, newDegree);
        if (newDegree === 0) queue.push(neighbor);
      }
    }
    queue.sort((a, b) => (importance[b] || 0) - (importance[a] || 0));
    currentLevel++;
  }

  edges.forEach(edge => {
    const srcLevel = levels.get(edge.source);
    const tgtLevel = levels.get(edge.target);
    if (srcLevel !== undefined && tgtLevel !== undefined && srcLevel >= tgtLevel) {
      console.warn(`Некорректная зависимость: ${edge.source} -> ${edge.target}`);
    }
  });

  nodes.forEach(node => {
    if (!levels.has(node.id)) levels.set(node.id, 0);
  });

  return levels;
}

function getLayoutedElements(nodes, edges, importance) {
  const levels = computeLevels(nodes, edges, importance);
  const nodesByLevel = new Map();

  for (const node of nodes) {
    const level = levels.get(node.id);
    if (!nodesByLevel.has(level)) nodesByLevel.set(level, []);
    nodesByLevel.get(level).push(node);
  }

  const levelHeight = 400;
  const nodeWidth = 150;
  const horizontalGap = 30;
  const layoutedNodes = [];

  const sortedLevels = Array.from(nodesByLevel.keys()).sort((a, b) => a - b);

  for (const level of sortedLevels) {
    const levelNodes = nodesByLevel.get(level);
    levelNodes.sort((a, b) => (importance[b.id] || 0) - (importance[a.id] || 0));

    const totalWidth = levelNodes.length * (nodeWidth + horizontalGap) - horizontalGap;
    let startX = -totalWidth / 2;

    levelNodes.forEach((node, idx) => {
      layoutedNodes.push({
        ...node,
        position: {
          x: startX + idx * (nodeWidth + horizontalGap),
          y: level * levelHeight,
        },
      });
    });
  }

  return { nodes: layoutedNodes, edges };
}

export default function SkillGraph({ graphData }) {
  if (!graphData || !graphData.nodes || !graphData.edges) {
    return <div>Нет данных для отображения графа</div>;
  }

  // Фильтруем уже изученные узлы и связанные с ними рёбра
  const filteredNodes = useMemo(() => 
    graphData.nodes.filter(node => !node.data?.is_known),
    [graphData.nodes]
  );

  const filteredNodeIds = useMemo(() => 
    new Set(filteredNodes.map(n => n.id)),
    [filteredNodes]
  );

  const filteredEdges = useMemo(() => 
    graphData.edges.filter(edge => 
      filteredNodeIds.has(edge.source) && filteredNodeIds.has(edge.target)
    ),
    [graphData.edges, filteredNodeIds]
  );

  const importance = useMemo(() => {
    const imp = {};
    filteredNodes.forEach(node => {
      imp[node.id] = node.data?.importance || 0;
    });
    return imp;
  }, [filteredNodes]);

  const { nodes, edges } = useMemo(
    () => getLayoutedElements(filteredNodes, filteredEdges, importance),
    [filteredNodes, filteredEdges, importance]
  );

  const defaultEdgeOptions = {
    type: 'default',
    animated: true,
    style: { stroke: '#1a5f9c', strokeWidth: 2 },
    markerEnd: { type: MarkerType.ArrowClosed, color: '#1a5f9c' },
  };

  const onNodeClick = useCallback((event, node) => {
    console.log('Clicked:', node.data.label);
  }, []);

  return (
    <div className="skill-graph-container">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodeClick={onNodeClick}
        nodeTypes={nodeTypes}
        defaultEdgeOptions={defaultEdgeOptions}
        fitView
      >
        <Background />
        <Controls />
        <MiniMap />
      </ReactFlow>
    </div>
  );
}