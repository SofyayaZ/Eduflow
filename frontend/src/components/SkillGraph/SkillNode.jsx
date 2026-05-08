// SkillNode.jsx
import React from 'react';
import { Handle, Position } from '@xyflow/react';

export default function SkillNode({ data }) {
  return (
    <div style={{
      padding: '10px',
      borderRadius: '8px',
      background: data.importance > 7 ? '#E3F2FD' : '#FFF',
      border: '2px solid #1a5f9c',
      minWidth: '120px',
      textAlign: 'center'
    }}>
      <Handle type="target" position={Position.Top} />
      <div style={{ fontWeight: 'bold' }}>{data.label}</div>
      <div style={{ fontSize: '12px', color: '#666' }}>Важность: {data.importance}</div>
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
}