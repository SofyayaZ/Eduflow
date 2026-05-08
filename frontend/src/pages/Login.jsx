import { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate, Link } from 'react-router-dom';

export default function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      await login(username, password);
      navigate('/profile');
    } catch (err) {
      setError('Неверное имя пользователя или пароль');
    }
  };

  return (
    <div className="auth-card">
      <h1>Вход</h1>
      <form onSubmit={handleSubmit}>
        <div className="field">
          <label>Имя пользователя</label>
          <input type="text" value={username} onChange={e => setUsername(e.target.value)} required />
        </div>
        <div className="field">
          <label>Пароль</label>
          <input type="password" value={password} onChange={e => setPassword(e.target.value)} required />
        </div>
        {error && <div style={{ color: 'red', marginBottom: '15px' }}>{error}</div>}
        <div className="actions">
          <button type="submit" className="btn btn-primary">Войти</button>
          <Link to="/register" className="btn btn-secondary">Регистрация</Link>
        </div>
      </form>
      <div className="back-link">
        <Link to="/">← Вернуться на главную</Link>
      </div>
    </div>
  );
}
