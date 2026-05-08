import { useNavigate } from 'react-router-dom';
import '../styles/pages/landing-page.css';


export default function Landing() {
  const navigate = useNavigate();
  return (
    <div className="container">
      <header>
        <div className="logo">EduPath</div>
        <div className="auth-buttons">
          <button className="register-btn" onClick={() => navigate('/register')}>Зарегистрироваться</button>
          <button className="login-btn" onClick={() => navigate('/login')}>Войти</button>
        </div>
      </header>

      <section className="hero">
        <h1>Построй свою карьеру</h1>
        <p>Персональные образовательные траектории<br />на основе данных рынка труда</p>
        <button className="btn-start" onClick={() => navigate('/register')}>Начать</button>
      </section>

      <section className="steps">
        <h2>Как это работает</h2>
        <div className="step-cards">
          <div className="card">
            <div className="step-number">1</div>
            <h3>Вводите навыки</h3>
            <p>Укажите текущие навыки и желаемую должность</p>
          </div>
          <div className="arrow">→</div>
          <div className="card">
            <div className="step-number">2</div>
            <h3>Анализируем</h3>
            <p>Собираем требования из тысяч вакансий</p>
          </div>
          <div className="arrow">→</div>
          <div className="card">
            <div className="step-number">3</div>
            <h3>Получаете план</h3>
            <p>Готовый пошаговый план обучения</p>
          </div>
        </div>
      </section>
      
      <footer>
        <div className="footer-links">
          <a href="#">О проекте</a>
          <a href="#">FAQ</a>
          <a href="#">Контакты</a>
          <a href="#">Политика конфиденциальности</a>
        </div>
        <div className="copyright">© 2026 EduPath. Все права защищены.</div>
      </footer>
    </div>
  );
}