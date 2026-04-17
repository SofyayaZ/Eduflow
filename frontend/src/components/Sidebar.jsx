import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

export default function Sidebar() {
  const { logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/');
  };

  return (
    <div className="sidebar">
      <div className="sidebar-logo">EduFlow</div>
      <nav className="sidebar-nav">
        <Link to="/profile" className="sidebar-link">Профиль</Link>
        <Link to="/generate" className="sidebar-link">Траектория</Link>
        <Link to="/history" className="sidebar-link">История</Link>
        <button onClick={handleLogout} className="sidebar-exit-btn">
          Выйти
        </button>
      </nav>
    </div>
  )
}