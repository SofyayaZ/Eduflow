import { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import api from '../api';
import { useProfileData } from '../hooks/useProfileData';
import SkillsSection from '../components/SkillsSection';
import TargetsSection from '../components/TargetsSection';
import RegionSection from '../components/RegionSection';

const REGION_OPTIONS = ['Москва', 'Санкт-Петербург', 'Казань', 'Новосибирск', 'Екатеринбург'];

export default function Profile() {
  const { user, setUser } = useAuth();
  const navigate = useNavigate();
  const [region, setRegion] = useState(user?.preferred_region || 'Москва');
  const {
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
  } = useProfileData();

  const updateRegion = async (newRegion) => {
    try {
      const { data } = await api.patch('/profile/', { preferred_region: newRegion });
      setUser(data);
      setRegion(data.preferred_region);
    } catch (err) {
      const errorMsg = err.response?.data?.message || err.response?.data?.error || 'Не удалось сохранить регион';
      alert(errorMsg);
    }
  };

  return (
    <div className="profile-page">
      <h1>Профиль</h1>

      <SkillsSection
        skills={skills}
        allSkills={allSkills}
        loadingSkills={loadingSkills}
        loadingAllSkills={loadingAllSkills}
        onAddSkill={addSkill}
        onDeleteSkill={deleteSkill}
      />

      <TargetsSection
        targets={targets}
        allTargets={allTargets}
        loadingTargets={loadingTargets}
        loadingAllTargets={loadingAllTargets}
        onAddTarget={addTarget}
        onDeleteTarget={deleteTarget}
      />

      <RegionSection
        region={region}
        setRegion={setRegion}
        onUpdateRegion={updateRegion}
        regionOptions={REGION_OPTIONS}
      />

      <button className="build-btn" onClick={() => navigate('/generate')}>
        Построить траекторию
      </button>
    </div>
  );
}