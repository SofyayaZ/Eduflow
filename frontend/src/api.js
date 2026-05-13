import axios from 'axios';
import { jwtDecode } from 'jwt-decode';

// --------------------------------------------------------------
// Функция выхода
// --------------------------------------------------------------
const logout = () => {
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
  window.location.href = '/login';
};

// ----------------------------------------------
//  Создание экземпляра api
// ----------------------------------------------
const api = axios.create({
  baseURL: '/api/v1/',
});

let isRefreshing = false;
let failedQueue = [];

const processQueue = (error, token = null) => {
  failedQueue.forEach(prom => {
    if (error) prom.reject(error);
    else prom.resolve(token);
  });
  failedQueue = [];
};


// ----------------------------------------------
//  Функция обновления токена (без использования api)
// ----------------------------------------------
const refreshToken = async () => {
  const refresh = localStorage.getItem('refresh_token');
  if (!refresh) throw new Error('No refresh token');
  const { data } = await axios.post('/api/v1/token/refresh/', { refresh });
  localStorage.setItem('access_token', data.access);
  return data.access;
};

// ----------------------------------------------
//  Проверка истёкшего токена
// ----------------------------------------------
const isTokenExpired = (token) => {
  if (!token) return true;
  try {
    const decoded = jwtDecode(token);
    return decoded.exp < Date.now() / 1000;
  } catch {
    return true;
  }
};

// ----------------------------------------------
//  Request interceptor
// ----------------------------------------------
api.interceptors.request.use(
  async (config) => {
    let token = localStorage.getItem('access_token');
    
    if (token && isTokenExpired(token)) {
      // Токен истёк – пытаемся обновить
      if (!isRefreshing) {
        isRefreshing = true;
        try {
          const newToken = await refreshToken();
          token = newToken;
          processQueue(null, newToken);
        } catch (err) {
          processQueue(err, null);
          logout();          // редирект на страницу входа
          throw err;
        } finally {
          isRefreshing = false;
        }
      } else {
        // Уже идёт обновление – ждём в очереди
        try {
          await new Promise((resolve, reject) => {
            failedQueue.push({ resolve, reject });
          });
          token = localStorage.getItem('access_token');
        } catch (err) {
          // Если обновление не удалось, пробрасываем ошибку дальше
          throw err;
        }
      }
    }
    
    // Устанавливаем токен в заголовок (важно!)
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// ----------------------------------------------
//  Response interceptor (страховка от 401)
// ----------------------------------------------
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    if (error.response?.status !== 401 || originalRequest._retry) {
      return Promise.reject(error);
    }
    originalRequest._retry = true;
    try {
      const newToken = await refreshToken();
      originalRequest.headers.Authorization = `Bearer ${newToken}`;
      return api(originalRequest);
    } catch (refreshError) {
      logout();
      return Promise.reject(refreshError);
    }
  }
);

export default api;
