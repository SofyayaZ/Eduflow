import { useState } from 'react';
import api from '../api';

export function useGeneratePath() {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');

  const generate = async (targetId) => {
    if (!targetId) return;
    setLoading(true);
    setErrorMessage('');
    try {
      const { data } = await api.post('/generate-path/', { job_target_id: targetId });
      setResult(data);
    } catch (err) {
      const message = err.response?.data?.error || err.response?.data?.message || 'Не удалось построить траекторию';
      setErrorMessage(message);
      setResult(null);
    } finally {
      setLoading(false);
    }
  };

  return { result, loading, errorMessage, generate };
}