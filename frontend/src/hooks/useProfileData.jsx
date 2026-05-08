// hooks/useProfileData.js
import { useState, useEffect } from 'react';
import api from '../api';

export function useProfileData() {
  const [skills, setSkills] = useState([]);
  const [targets, setTargets] = useState([]);
  const [allSkills, setAllSkills] = useState([]);
  const [allTargets, setAllTargets] = useState([]);
  const [loadingSkills, setLoadingSkills] = useState(true);
  const [loadingTargets, setLoadingTargets] = useState(true);
  const [loadingAllSkills, setLoadingAllSkills] = useState(true);
  const [loadingAllTargets, setLoadingAllTargets] = useState(true);

  const loadUserSkills = async () => {
    setLoadingSkills(true);
    try {
      const { data } = await api.get('/user-skills/');
      setSkills(data);
    } catch {
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
    } catch {
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
    } catch {
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
    } catch {
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

  const deleteSkill = async (id) => {
    try {
      await api.delete(`/user-skills/${id}/`);
      await loadUserSkills();
    } catch {
      alert('Не удалось удалить навык');
    }
  };

  const deleteTarget = async (id) => {
    try {
      await api.delete(`/user-targets/${id}/`);
      await loadUserTargets();
    } catch {
      alert('Не удалось удалить цель');
    }
  };

  const addSkill = async (skillId) => {
    try {
      await api.post('/user-skills/', { skill_id: skillId });
      await loadUserSkills();
      return { success: true };
    } catch (err) {
      if (err.response?.status === 400) alert('Этот навык уже есть у вас');
      else alert('Не удалось добавить навык');
      return { success: false };
    }
  };

  const addTarget = async (targetId) => {
    try {
      await api.post('/user-targets/', { target_job_id: targetId });
      await loadUserTargets();
      return { success: true };
    } catch (err) {
      if (err.response?.status === 400) alert('Эта цель уже добавлена');
      else alert('Не удалось добавить цель');
      return { success: false };
    }
  };

  return {
    skills,
    targets,
    allSkills,
    allTargets,
    loadingSkills,
    loadingTargets,
    loadingAllSkills,
    loadingAllTargets,
    deleteSkill,
    deleteTarget,
    addSkill,
    addTarget,
  };
}