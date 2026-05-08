import React, { useCallback, useEffect, useMemo } from 'react';
import { ReactFlow, Background, Controls, MiniMap, useNodesState, useEdgesState, addEdge } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import SkillNode from './SkillNode';

const nodeTypes = { skillNode: SkillNode };

// ---------- Расчёт уровней (topological ordering с учётом важности) ----------
function computeLevels(nodes, edges, importance = {}) {
  // Строим граф зависимостей: для каждого узла список тех, кто от него зависит (outgoing)
  const graph = new Map(); // key: sourceId, value: array of targetIds
  const inDegree = new Map(); // количество входящих рёбер (незакрытых пререквизитов)

  // Инициализация
  nodes.forEach(node => {
    graph.set(node.id, []);
    inDegree.set(node.id, 0);
  });

  edges.forEach(edge => {
    graph.get(edge.source).push(edge.target);
    inDegree.set(edge.target, inDegree.get(edge.target) + 1);
  });

  // Находим узлы с нулевой степенью входа (корни)
  const queue = [];
  for (let [nodeId, degree] of inDegree.entries()) {
    if (degree === 0) queue.push(nodeId);
  }

  // Сортируем очередь по важности (убывание), чтобы более важные шли первыми
  queue.sort((a, b) => (importance[b] || 0) - (importance[a] || 0));

  const levels = new Map(); // nodeId -> level
  let currentLevel = 0;

  while (queue.length) {
    const levelSize = queue.length;
    for (let i = 0; i < levelSize; i++) {
      const nodeId = queue.shift();
      levels.set(nodeId, currentLevel);

      // Уменьшаем inDegree для соседей
      for (const neighbor of graph.get(nodeId)) {
        const newDegree = inDegree.get(neighbor) - 1;
        inDegree.set(neighbor, newDegree);
        if (newDegree === 0) {
          queue.push(neighbor);
        }
      }
    }
    // Сортируем новую очередь по важности перед следующим уровнем
    queue.sort((a, b) => (importance[b] || 0) - (importance[a] || 0));
    currentLevel++;
  }

  // Если остались узлы с циклами (не должны возникать), отдаём уровень 0
  for (const node of nodes) {
    if (!levels.has(node.id)) levels.set(node.id, 0);
  }

  return levels;
}

// ---------- Позиционирование узлов по уровням ----------
function getLayoutedElements(nodes, edges, importance) {
  const levels = computeLevels(nodes, edges, importance);

  // Группируем узлы по уровням
  const nodesByLevel = new Map();
  for (const node of nodes) {
    const level = levels.get(node.id);
    if (!nodesByLevel.has(level)) nodesByLevel.set(level, []);
    nodesByLevel.get(level).push(node);
  }

  // Настройки отступов
  const levelHeight = 120;    // расстояние между уровнями по Y
  const nodeWidth = 150;
  const nodeHeight = 50;
  const horizontalGap = 30;   // между узлами на одном уровне

  const layoutedNodes = [];

  for (const [level, levelNodes] of nodesByLevel.entries()) {
    // Сортируем узлы на уровне по важности (убывание) — слева направо
    levelNodes.sort((a, b) => (importance[b.id] || 0) - (importance[a.id] || 0));

    const totalWidth = levelNodes.length * (nodeWidth + horizontalGap) - horizontalGap;
    let startX = -totalWidth / 2; // центрируем по X

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

// ---------- Компонент SkillGraph ----------
export default function SkillGraph({ graphData }) {
  if (!graphData || !graphData.nodes || !graphData.edges) {
    return <div>Нет данных для отображения графа</div>;
  }

  // Извлекаем importance из data узлов (если есть)
  const importance = {};
  graphData.nodes.forEach(node => {
    importance[node.id] = node.data?.importance || 0;
  });

  // Вычисляем layout с уровнями
  const { nodes: layoutedNodes, edges: layoutedEdges } = useMemo(
    () => getLayoutedElements(graphData.nodes, graphData.edges, importance),
    [graphData]
  );

  const [nodes, setNodes, onNodesChange] = useNodesState(layoutedNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(layoutedEdges);

  useEffect(() => {
    const { nodes: newNodes, edges: newEdges } = getLayoutedElements(
      graphData.nodes,
      graphData.edges,
      importance
    );
    setNodes(newNodes);
    setEdges(newEdges);
  }, [graphData, setNodes, setEdges]);

  const onConnect = useCallback((params) => setEdges((eds) => addEdge(params, eds)), [setEdges]);
  const onNodeClick = useCallback((event, node) => {
    console.log('Clicked:', node.data.label);
  }, []);

  return (
    <div style={{ height: '600px', width: '100%' }}>
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
        <MiniMap />
      </ReactFlow>
    </div>
  );
}