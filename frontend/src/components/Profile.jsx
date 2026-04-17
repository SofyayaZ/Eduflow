import { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import api from '../api';

export default function Profile() {
  const { user, setUser } = useAuth();
  const navigate = useNavigate();

  // Состояния данных
  const [skills, setSkills] = useState([]);
  const [targets, setTargets] = useState([]);
  const [allSkills, setAllSkills] = useState([]);
  const [allTargets, setAllTargets] = useState([]);
  const [region, setRegion] = useState(user?.preferred_region || 'Москва');

  // Состояния загрузки
  const [loadingSkills, setLoadingSkills] = useState(true);
  const [loadingTargets, setLoadingTargets] = useState(true);
  const [loadingAllSkills, setLoadingAllSkills] = useState(true);
  const [loadingAllTargets, setLoadingAllTargets] = useState(true);
  const [addingSkill, setAddingSkill] = useState(false);
  const [addingTarget, setAddingTarget] = useState(false);

  // Поисковые запросы
  const [skillSearch, setSkillSearch] = useState('');

  // Выбранные ID
  const [selectedSkillId, setSelectedSkillId] = useState('');
  const [selectedTargetId, setSelectedTargetId] = useState('');

  // --- Загрузка данных с обработкой ошибок ---
  const loadUserSkills = async () => {
    setLoadingSkills(true);
    try {
      const { data } = await api.get('/user-skills/');
      setSkills(data);
    } catch (err) {
      console.error('Failed to load user skills', err);
      alert('Не удалось загрузить навыки пользователя');
    } finally {
      setLoadingSkills(false);
    }
  };

  const loadUserTargets = async () => {
    setLoadingTargets(true);
    try {
      const { data } = await api.get('/user-targets/');
      setTargets(data);
    } catch (err) {
      console.error('Failed to load user targets', err);
      alert('Не удалось загрузить цели пользователя');
    } finally {
      setLoadingTargets(false);
    }
  };

  const loadAllSkills = async () => {
    setLoadingAllSkills(true);
    try {
      const { data } = await api.get('/skills/');
      setAllSkills(data);
    } catch (err) {
      console.error('Failed to load all skills', err);
      alert('Не удалось загрузить список навыков');
    } finally {
      setLoadingAllSkills(false);
    }
  };

  const loadAllTargets = async () => {
    setLoadingAllTargets(true);
    try {
      const { data } = await api.get('/job-targets/');
      setAllTargets(data);
    } catch (err) {
      console.error('Failed to load all targets', err);
      alert('Не удалось загрузить список целей');
    } finally {
      setLoadingAllTargets(false);
    }
  };

  useEffect(() => {
    loadUserSkills();
    loadUserTargets();
    loadAllSkills();
    loadAllTargets();
  }, []);

  // --- Обновление региона ---
  const updateRegion = async () => {
    try {
      const { data } = await api.patch('/profile/', { preferred_region: region });
      setUser(data);
      setRegion(data.preferred_region);
    } catch (err) {
      console.error('Failed to update region', err.response?.data || err.message);
      const errorMsg = err.response?.data?.message || err.response?.data?.error || 'Не удалось сохранить регион';
      alert(errorMsg);
    }
  };

  // --- Добавление навыка с обработкой дубликата ---
  const handleAddSkill = async () => {
    if (!selectedSkillId) return;
    setAddingSkill(true);
    try {
      await api.post('/user-skills/', { skill_id: selectedSkillId });
      setSelectedSkillId('');
      setSkillSearch('');        // очищаем поиск
      await loadUserSkills();    // обновляем список навыков пользователя
      // Дополнительно обновляем allSkills? Необязательно, т.к. он не меняется
    } catch (err) {
      if (err.response && err.response.status === 400) {
        alert('Этот навык уже есть у вас');
      } else {
        alert('Не удалось добавить навык');
      }
    } finally {
      setAddingSkill(false);
    }
  };

  const deleteSkill = async (id) => {
    try {
      await api.delete(`/user-skills/${id}/`);
      await loadUserSkills();
    } catch (err) {
      alert('Не удалось удалить навык');
    }
  };

  // --- Добавление цели с обработкой дубликата ---
  const handleAddTarget = async () => {
    if (!selectedTargetId) return;
    setAddingTarget(true);
    try {
      await api.post('/user-targets/', { target_job_id: selectedTargetId });
      setSelectedTargetId('');
      await loadUserTargets();
    } catch (err) {
      if (err.response && err.response.status === 400) {
        alert('Эта цель уже добавлена');
      } else {
        alert('Не удалось добавить цель');
      }
    } finally {
      setAddingTarget(false);
    }
  };

  const deleteTarget = async (id) => {
    try {
      await api.delete(`/user-targets/${id}/`);
      await loadUserTargets();
    } catch (err) {
      alert('Не удалось удалить цель');
    }
  };

  // Фильтрация доступных навыков/целей по поисковому запросу
  const availableSkills = allSkills.filter(
    skill => !skills.some(us => us.skill.id === skill.id)
  );
  const filteredSkills = availableSkills.filter(skill =>
    skill.name.toLowerCase().includes(skillSearch.toLowerCase())
  );

  const availableTargets = allTargets.filter(
    target => !targets.some(ut => ut.target_job.id === target.id)
  );

  const filteredTargets = availableTargets;
  const regionOptions = ['Москва', 'Санкт-Петербург', 'Казань', 'Новосибирск', 'Екатеринбург'];
  const [showSkillDropdown, setShowSkillDropdown] = useState(false);
  const selectSkill = async (skill) => {
    // Закрываем выпадающий список
    setShowSkillDropdown(false);
    
    // Проверяем, не добавляем ли уже (защита от двойного клика)
    if (addingSkill) return;
    
    setAddingSkill(true);
    try {
      await api.post('/user-skills/', { skill_id: skill.id });
      // Очищаем поиск и выбранный ID
      setSkillSearch('');
      setSelectedSkillId('');
      // Обновляем список навыков пользователя
      await loadUserSkills();
    } catch (err) {
      if (err.response && err.response.status === 400) {
        alert('Этот навык уже есть у вас');
      } else {
        alert('Не удалось добавить навык');
      }
    } finally {
      setAddingSkill(false);
    }
  };

  const selectTarget = (target) => {
    setSelectedTargetId(target.id);
    setTargetSearch(target.name);
    setShowTargetDropdown(false);
  };

  return (
    <div className="profile-page">
      <h1>Профиль</h1>

      {/* Блок навыков */}
      <div className="section">
        <h2>Мои навыки</h2>
        {loadingSkills ? (
          <p>Загрузка навыков...</p>
        ) : (
          <>
            {skills.length === 0 && <p style={{ color: '#7f8c8d' }}>Навыки не добавлены</p>}
            {skills.map(s => (
              <div key={s.id} className="list-item">
                <span className="skill-name">{s.skill.name}</span>
                <button className="delete-btn" onClick={() => deleteSkill(s.id)}>✕</button>
              </div>
            ))}
          </>
        )}
        
        <div style={{ marginTop: '20px', position: 'relative' }}>
          {loadingAllSkills ? (
            <p>Загрузка списка навыков...</p>
          ) : (
            <>
              <input
                type="text"
                className="skill-search-input"
                placeholder="Начните вводить название навыка..."
                value={skillSearch}
                onChange={e => {
                  setSkillSearch(e.target.value);
                  setShowSkillDropdown(true);
                  if (selectedSkillId) setSelectedSkillId('');
                }}
                onFocus={() => setShowSkillDropdown(true)}
                onBlur={() => setTimeout(() => setShowSkillDropdown(false), 150)}
              />
              {showSkillDropdown && skillSearch.trim() !== '' && (
                <ul className="autocomplete-dropdown">
                  {filteredSkills.length === 0 && (
                    <li className="autocomplete-no-results">Ничего не найдено</li>
                  )}
                  {filteredSkills.map(skill => (
                    <li key={skill.id} onClick={() => selectSkill(skill)} className="autocomplete-item">
                      {skill.name}
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
        </div>
      </div>

      {/* Блок целей */}
      <div className="section">
        <h2>Мои цели</h2>
        {loadingTargets ? (
          <p>Загрузка целей...</p>
        ) : (
          <>
            {targets.length === 0 && <p style={{ color: '#7f8c8d' }}>Цели не добавлены</p>}
            {targets.map(t => (
              <div key={t.id} className="list-item">
                <span className="goal-name">{t.target_job.name}</span>
                <button className="delete-btn" onClick={() => deleteTarget(t.id)}>✕</button>
              </div>
            ))}
          </>
        )}

        <div style={{ marginTop: '20px' }}>
          {loadingAllTargets ? (
            <p>Загрузка списка целей...</p>
          ) : (
            <>
              {availableTargets.length === 0 ? (
                <div className="info-message" style={{ textAlign: 'center', padding: '12px' }}>
                  Все доступные цели добавлены
                </div>
              ) : (
                <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
                  <select
                    className="region-select"
                    value={selectedTargetId}
                    onChange={e => setSelectedTargetId(e.target.value)}
                    style={{ flex: 1 }}
                  >
                    <option value="">-- Выберите цель --</option>
                    {availableTargets.map(target => (
                      <option key={target.id} value={target.id}>{target.name}</option>
                    ))}
                  </select>
                  <button
                    className="btn btn-primary"
                    onClick={handleAddTarget}
                    disabled={!selectedTargetId || addingTarget}
                    style={{ whiteSpace: 'nowrap' }}
                  >
                    {addingTarget ? 'Добавление...' : 'Добавить цель'}
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* Регион */}
      <div className="section">
        <h2>Регион обзора вакансий</h2>
        <select className="region-select" value={region} onChange={e => setRegion(e.target.value)} onBlur={updateRegion}>
          {regionOptions.map(r => <option key={r} value={r}>{r}</option>)}
        </select>
        <div className="region-info">
          Выбранный регион будет использоваться при анализе вакансий.
        </div>
      </div>

      <button className="build-btn" onClick={() => navigate('/generate')}>
        Построить траекторию
      </button>
    </div>
  );
}