import '../styles/components/goal-selector.css';


export default function GoalSelector({ targets, selectedTargetId, onSelectTarget, onGenerate, isLoading }) {
  return (
    <div className="goal-selector">
      <label>Активная цель</label>
      <div className="goal-options">
        {targets.map(ut => (
          <div
            key={ut.id}
            className={`goal-radio ${selectedTargetId === ut.id ? 'selected' : ''}`}
            onClick={() => onSelectTarget(ut.id)}
          >
            <input type="radio" name="goal" checked={selectedTargetId === ut.id} readOnly />
            <span className="target-label">{ut.target_job.name}</span>
          </div>
        ))}
      </div>
      <button className="build-btn" onClick={onGenerate} disabled={!selectedTargetId || isLoading}>
        {isLoading ? 'Загрузка...' : 'Построить траекторию'}
      </button>
    </div>
  );
}