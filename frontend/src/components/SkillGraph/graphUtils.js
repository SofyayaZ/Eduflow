import dagre from 'dagre';

// Функция для преобразования дерева от API в формат React Flow с расчетом позиций
export const transformTreeToGraph = (treeData) => {
  const nodes = [];
  const edges = [];
  // Используем dagre для автоматической раскладки графа
  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));
  // Устанавливаем направление графа: сверху вниз
  dagreGraph.setGraph({ rankdir: 'TB' });

  // Рекурсивная функция для обхода дерева
  const traverse = (node, parentId = null) => {
    const nodeId = String(node.skill.id);
    // Добавляем узел, если его еще нет
    if (!nodes.find(n => n.id === nodeId)) {
      // Пока задаем временную позицию, dagre пересчитает
      const newNode = {
        id: nodeId,
        data: { 
          label: node.skill.name,
          importance: node.importance
        },
        position: { x: 0, y: 0 },
        style: { 
          background: node.importance > 7 ? '#E3F2FD' : '#FFF',
          border: '1px solid #1a5f9c',
          borderRadius: '8px',
          padding: '10px'
        }
      };
      nodes.push(newNode);
      dagreGraph.setNode(nodeId, { width: 150, height: 50 });
    }

    // Добавляем ребро к родителю
    if (parentId) {
      const edgeId = `${parentId}-${nodeId}`;
      if (!edges.find(e => e.id === edgeId)) {
        edges.push({
          id: edgeId,
          source: parentId,
          target: nodeId,
          type: 'smoothstep', // Тип линии
          animated: true,      // Анимированная линия
          style: { stroke: '#1a5f9c', strokeWidth: 2 },
        });
        dagreGraph.setEdge(parentId, nodeId);
      }
    }

    // Рекурсивно обходим детей
    if (node.children && node.children.length) {
      node.children.forEach(child => traverse(child, nodeId));
    }
  };

  treeData.forEach(root => traverse(root));

  // Применяем расчет позиций с помощью dagre
  dagre.layout(dagreGraph);
  nodes.forEach(node => {
    const nodeWithPosition = dagreGraph.node(node.id);
    node.position = {
      x: nodeWithPosition.x - (nodeWithPosition.width / 2),
      y: nodeWithPosition.y - (nodeWithPosition.height / 2),
    };
  });

  return { nodes, edges };
};