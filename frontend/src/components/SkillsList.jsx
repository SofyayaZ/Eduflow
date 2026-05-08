export default function SkillsList({ title, skills, variant = 'default' }) {
  if (!skills || skills.length === 0) return null;
  const className = variant === 'soft' ? 'info-note soft-skills' : 'info-note';
  return (
    <div className={className}>
      <strong>{title}</strong> {skills.map(s => s.name).join(', ')}
    </div>
  );
}