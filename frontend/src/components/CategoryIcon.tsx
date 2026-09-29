const iconOffsets = {
  olympiad: 20,
  school: 238,
  career: 487.5,
  hackathon: 697,
} as const;

export function CategoryIcon({ kind }: { kind: keyof typeof iconOffsets }) {
  // Keep the two original Figma exports intact. Each slot displays its 98px circle
  // at half scale and clips the other circles and labels from the export.
  const style = { left: -iconOffsets[kind] / 2 };

  return (
    <span className="category-icon" aria-hidden="true">
      <img className="category-art category-art--light" src="/assets/figma/categories-light.svg" width="815" height="169" style={style} alt="" />
      <img className="category-art category-art--selected" src="/assets/figma/categories-selected.svg" width="815" height="169" style={style} alt="" />
    </span>
  );
}
