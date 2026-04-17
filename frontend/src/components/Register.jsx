import { useState } from 'react';
import api from '../api';
import { useNavigate, Link } from 'react-router-dom';

export default function Register() {
  const [form, setForm] = useState({ username: '', email: '', password: '' });
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      await api.post('/register/', form);
      navigate('/login');
    } catch (err) {
      setError('Ошибка регистрации. Возможно, имя уже занято.');
    }
  };

  return (
    <div className="auth-card">
      <h1>Регистрация</h1>
      <form onSubmit={handleSubmit}>
        <div className="field">
          <label>Имя пользователя</label>
          <input type="text" value={form.username} onChange={e => setForm({...form, username: e.target.value})} required />
        </div>
        <div className="field">
          <label>Email</label>
          <input type="email" value={form.email} onChange={e => setForm({...form, email: e.target.value})} required />
        </div>
        <div className="field">
          <label>Пароль</label>
          <input type="password" value={form.password} onChange={e => setForm({...form, password: e.target.value})} required />
        </div>
        {error && <div style={{ color: 'red', marginBottom: '15px' }}>{error}</div>}
        <div className="actions">
          <button type="submit" className="btn btn-primary">Зарегистрироваться</button>
          <Link to="/login" className="btn btn-secondary">Вход</Link>
        </div>
      </form>
      <div className="back-link">
        <Link to="/">← Вернуться на главную</Link>
      </div>
    </div>
  );
}
