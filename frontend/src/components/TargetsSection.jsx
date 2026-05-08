import { useState } from 'react';

export default function TargetsSection({ targets, allTargets, loadingTargets, loadingAllTargets, onAddTarget, onDeleteTarget }) {
  const [selectedTargetId, setSelectedTargetId] = useState('');
  const [adding, setAdding] = useState(false);

  const availableTargets = allTargets.filter(target => !targets.some(ut => ut.target_job.id === target.id));

  const handleAdd = async () => {
    if (!selectedTargetId || adding) return;
    setAdding(true);
    await onAddTarget(selectedTargetId);
    setSelectedTargetId('');
    setAdding(false);
  };

  return (
    <div className="section">
      <h2>Мои цели</h2>
      {loadingTargets ? (
        <p>Загрузка целей...</p>
      ) : (
        <>
          {targets.length === 0 && <p style={{ color: '#7f8c8d' }}>Цели не добавлены</p>}
          {targets.map(t => (
            <div key={t.id} className="list-item">
              <span className="goal-name">{t.target_job.name}</span>
              <button className="delete-btn" onClick={() => onDeleteTarget(t.id)}>✕</button>
            </div>
          ))}
        </>
      )}
      <div style={{ marginTop: '20px' }}>
        {loadingAllTargets ? (
          <p>Загрузка списка целей...</p>
        ) : (
          <>
            {availableTargets.length === 0 ? (
              <div className="info-message" style={{ textAlign: 'center', padding: '12px' }}>
                Все доступные цели добавлены
              </div>
            ) : (
              <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
                <select
                  className="region-select"
                  value={selectedTargetId}
                  onChange={e => setSelectedTargetId(e.target.value)}
                  style={{ flex: 1 }}
                >
                  <option value="">-- Выберите цель --</option>
                  {availableTargets.map(target => (
                    <option key={target.id} value={target.id}>{target.name}</option>
                  ))}
                </select>
                <button
                  className="btn btn-primary"
                  onClick={handleAdd}
                  disabled={!selectedTargetId || adding}
                  style={{ whiteSpace: 'nowrap' }}
                >
                  {adding ? 'Добавление...' : 'Добавить цель'}
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}