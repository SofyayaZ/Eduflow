import React from 'react';
import { Handle, Position } from '@xyflow/react';
import '../../styles/components/skill-node.css';

export default function SkillNode({ data }) {
  const importanceClass = data.importance > 7 
    ? 'skill-node--high-importance' 
    : 'skill-node--normal-importance';

  return (
    <div className={`skill-node ${importanceClass}`}>
      <Handle type="target" position={Position.Top} />
      <div className="skill-node__title">{data.label}</div>
      <div className="skill-node__importance">Важность: {data.importance}</div>
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
}