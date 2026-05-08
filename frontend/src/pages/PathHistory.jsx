import { useState, useEffect } from 'react';
import api from '../api';
import { Link } from 'react-router-dom';

import '../styles/pages/path-history-page.css'


export default function PathHistory() {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadHistory();
  }, []);

  const loadHistory = async () => {
    setLoading(true);
    setError(null);
    try {
      const { data } = await api.get('/path-history/');
      setHistory(data);
    } catch (err) {
      console.error('Failed to load history', err);
      setError('Не удалось загрузить историю траекторий');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="history-page" style={{ textAlign: 'center' }}>Загрузка...</div>;
  }

  if (error) {
    return (
      <div className="history-page" style={{ textAlign: 'center', color: 'red' }}>
        <p>{error}</p>
        <button onClick={loadHistory} className="btn btn-primary">Повторить</button>
      </div>
    );
  }

  return (
    <div className="history-page">
      <h1>История траекторий</h1>
      {history.length === 0 ? (
        <div className="empty-history">
          <p>У вас пока нет сохранённых траекторий.</p>
          <Link to="/generate" className="btn btn-primary" style={{ marginTop: '20px', display: 'inline-block' }}>
            Построить первую траекторию
          </Link>
        </div>
      ) : (
        <div className="history-list">
          {history.map(path => (
            <div key={path.id} className={`history-card ${path.is_current ? 'current' : ''}`}>
              <div className="history-header">
                <div>
                  <span className="history-target">{path.target.target_job.name}</span>
                  {path.is_current && <span className="current-badge">Текущая траектория</span>}
                </div>
                <div className="history-date">
                  {new Date(path.generated_at).toLocaleString()}
                </div>
              </div>
              <div className="history-steps">
                <h4>Шаги для изучения:</h4>
                <ul className="steps-list">
                  {path.steps.map(step => (
                    <li key={step.order} className="step-item">
                      {step.order}. {step.skill}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}