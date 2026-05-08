import { useState, useEffect, useMemo } from 'react';
import api from '../api';
import SkillGraph from '../components/SkillGraph';
import GoalSelector from '../components/GoalSelector';
import SkillsList from '../components/SkillsList';
import { useGeneratePath } from '../hooks/useGeneratePath';
import '../styles/components/path-steps.css'
import '../styles/pages/generate-path-page.css'


export default function GeneratePath() {
  const [userTargets, setUserTargets] = useState([]);
  const [selectedTargetId, setSelectedTargetId] = useState('');
  const { result, loading, errorMessage, generate } = useGeneratePath();

  useEffect(() => {
    api.get('/user-targets/').then(res => setUserTargets(res.data));
  }, []);

  const hardMissingSkills = useMemo(() => {
    if (!result?.missing_skills) return [];
    const softIds = new Set((result.soft_skills || []).map(s => s.id));
    return result.missing_skills.filter(skill => !softIds.has(skill.id));
  }, [result]);

  const handleGenerate = () => generate(selectedTargetId);

  return (
    <div className="path-page">
      <h1>Построение траектории</h1>
      <div className="subtitle">Выберите цель, чтобы сформировать план обучения</div>

      <GoalSelector
        targets={userTargets}
        selectedTargetId={selectedTargetId}
        onSelectTarget={setSelectedTargetId}
        onGenerate={handleGenerate}
        isLoading={loading}
      />

      {errorMessage && <div className="error-message">{errorMessage}</div>}

      {result?.ordered_steps && result.ordered_steps.length > 0 && (
        <div className="steps-plan">
          <h3 className="steps-title">Первые 10 шагов</h3>
          <div className="steps-grid">
            {result.ordered_steps.map(step => (
              <div key={step.id} className="step-card">
                <div className="step-number">{step.order}</div>
                <div className="step-name">{step.name}</div>
              </div>
            ))}
          </div>
        </div>
      )}


      <div className="graph-container">
        {result ? (
          result.message ? (
            <div className="info-message">{result.message}</div>
          ) : (
            <>
              <h3 className="graph-title">Граф зависимостей навыков</h3>
              {result.graph && result.graph.edges && result.graph.edges.length > 0 ? (
                <SkillGraph graphData={result.graph} />
              ) : (
                <div className="info-message">Навыков, связанных между собой, не было выявлено</div>
              )}
            </>
          )
        ) : (
          <div className="placeholder-message">
            Нажмите «Построить траекторию», чтобы увидеть план обучения
          </div>
        )}
      </div>

      <SkillsList
        title="Мягкие навыки нужно развивать параллельно:"
        skills={result?.soft_skills || []}
        variant="soft"
      />
      <SkillsList
        title="Технические навыки без зависимостей можно изучать в любом порядке:"
        skills={result?.standalone_skills || []}
      />
    </div>
  );
}