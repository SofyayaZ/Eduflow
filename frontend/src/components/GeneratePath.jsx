import { useState, useEffect } from 'react';
import api from '../api';

export default function GeneratePath() {
  const [userTargets, setUserTargets] = useState([]);
  const [selectedTargetId, setSelectedTargetId] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');

  useEffect(() => {
    api.get('/user-targets/').then(res => setUserTargets(res.data));
  }, []);

  const generate = async () => {
    if (!selectedTargetId) return;
    setLoading(true);
    setErrorMessage('');

    try {
      const { data } = await api.post('/generate-path/', { job_target_id: selectedTargetId });
      setResult(data);
    } catch (err) {
      if (err.response) {
        const { status, data } = err.response;
        if (status === 404 && data?.message) {
          setErrorMessage(data.message);
        } else if (status === 400 && data?.error) {
          setErrorMessage(`Ошибка: ${data.error}`);
        } else {
          setErrorMessage('Произошла ошибка при генерации траектории');
        }
      } else {
        setErrorMessage('Не удалось соединиться с сервером');
      }
      setResult(null);
    } finally {
      setLoading(false);
    }
  };

  // Новая функция отображения – список шагов
  const renderPathSteps = () => {
    if (!result || !result.path || result.path.length === 0) return null;
    return (
      <div className="path-steps-list">
        <h3>Порядок изучения навыков:</h3>
        <ol className="steps-timeline">
          {result.path.map((step, idx) => (
            <li key={idx} className="step-timeline-item">
              <span className="step-number-badge">{idx + 1}</span>
              <span className="step-skill-name">{step.skill}</span>
            </li>
          ))}
        </ol>
      </div>
    );
  };

  return (
    <div className="path-page">
      <h1>Построение траектории</h1>
      <div className="subtitle">Выберите цель, чтобы сформировать пошаговый план обучения</div>

      <div className="goal-selector">
        <label>Активная цель</label>
        <div className="goal-options">
          {userTargets.map(ut => (
            <div
              key={ut.id}
              className={`goal-radio ${selectedTargetId === ut.id ? 'selected' : ''}`}
              onClick={() => setSelectedTargetId(ut.id)}
            >
              <input type="radio" name="goal" checked={selectedTargetId === ut.id} readOnly />
              <span className="target-label">{ut.target_job.name}</span>
            </div>
          ))}
        </div>
        <button className="build-btn" onClick={generate} disabled={!selectedTargetId || loading}>
          {loading ? 'Загрузка...' : 'Построить траекторию'}
        </button>
      </div>

      {errorMessage && (
        <div className="error-message">{errorMessage}</div>
      )}

      <div className="graph-container">
        {result ? (
          result.message ? (
            <div className="info-message">{result.message}</div>
          ) : (
            renderPathSteps()
          )
        ) : (
          <div className="placeholder-message">
            Нажмите «Построить траекторию», чтобы увидеть план обучения
          </div>
        )}
      </div>

      {result && result.missing_skills && result.missing_skills.length > 0 && (
        <div className="info-note">
          Недостающие навыки: {result.missing_skills.map(s => s.name).join(', ')}
        </div>
      )}
    </div>
  );
}