import { useState } from 'react';
import '../styles/components/skills-section.css'


export default function SkillsSection({ skills, allSkills, loadingSkills, loadingAllSkills, onAddSkill, onDeleteSkill }) {
  const [skillSearch, setSkillSearch] = useState('');
  const [showDropdown, setShowDropdown] = useState(false);
  const [adding, setAdding] = useState(false);

  const availableSkills = allSkills.filter(skill => !skills.some(us => us.skill.id === skill.id));
  const filteredSkills = availableSkills.filter(skill =>
    skill.name.toLowerCase().includes(skillSearch.toLowerCase())
  );

  const handleSelectSkill = async (skill) => {
    if (adding) return;
    setShowDropdown(false);
    setAdding(true);
    await onAddSkill(skill.id);
    setSkillSearch('');
    setAdding(false);
  };

  return (
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
              <button className="delete-btn" onClick={() => onDeleteSkill(s.id)}>✕</button>
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
                setShowDropdown(true);
              }}
              onFocus={() => setShowDropdown(true)}
              onBlur={() => setTimeout(() => setShowDropdown(false), 150)}
            />
            {showDropdown && skillSearch.trim() !== '' && (
              <ul className="autocomplete-dropdown">
                {filteredSkills.length === 0 && <li className="autocomplete-no-results">Ничего не найдено</li>}
                {filteredSkills.map(skill => (
                  <li key={skill.id} onClick={() => handleSelectSkill(skill)} className="autocomplete-item">
                    {skill.name}
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </div>
    </div>
  );
}