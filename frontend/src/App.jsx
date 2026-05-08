import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import Sidebar from './components/Sidebar';
import Landing from './pages/Landing';
import Login from './pages/Login';
import Register from './pages/Register';
import Profile from './pages/Profile';
import GeneratePath from './pages/GeneratePath';
import PathHistory from './pages/PathHistory';

// Стили
import './styles/globals.css';
import './styles/layout/header.css';
import './styles/layout/footer.css';
import './styles/layout/sidebar.css';
import './styles/components/info-note.css';
import './styles/components/buttons.css';
import './styles/components/forms.css';
import './styles/components/auth-card.css';


function AppRoutes() {
  const { user, loading } = useAuth();

  if (loading) {
    return <div style={{ textAlign: 'center', marginTop: '50px' }}>Загрузка...</div>;
  }

  // Если пользователь авторизован, рендерим с сайдбаром
  if (user) {
    return (
      <div style={{ display: 'flex' }}>
        <Sidebar />
        <div className="main-content">
          <Routes>
            <Route path="/" element={<Navigate to="/profile" replace />} />
            <Route path="/profile" element={<Profile />} />
            <Route path="/generate" element={<GeneratePath />} />
            <Route path="/history" element={<PathHistory />} />
            <Route path="*" element={<Navigate to="/profile" replace />} />
          </Routes>
        </div>
      </div>
    );
  }

  // Неавторизованный пользователь — без сайдбара (лендинг, логин, регистрация)
  return (
    <div className="main-content-full">
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </div>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;