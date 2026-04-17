// src/App.jsx
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import Sidebar from './components/Sidebar';
import Landing from './components/Landing';
import Login from './components/Login';
import Register from './components/Register';
import Profile from './components/Profile';
import GeneratePath from './components/GeneratePath';
import PathHistory from './components/PathHistory';

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