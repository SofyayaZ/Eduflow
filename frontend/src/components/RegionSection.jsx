import '../styles/components/region-section.css';


export default function RegionSection({ region, setRegion, onUpdateRegion, regionOptions }) {
  const handleBlur = () => {
    if (onUpdateRegion) onUpdateRegion(region);
  };

  return (
    <div className="section">
      <h2>Регион обзора вакансий</h2>
      <select className="region-select" value={region} onChange={e => setRegion(e.target.value)} onBlur={handleBlur}>
        {regionOptions.map(r => <option key={r} value={r}>{r}</option>)}
      </select>
      <div className="region-info">
        Выбранный регион будет использоваться при анализе вакансий.
      </div>
    </div>
  );
}