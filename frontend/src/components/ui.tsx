import type { ReactNode } from "react";
export function Choice({
  selected,
  onClick,
  children,
  className = "",
}: {
  selected: boolean;
  onClick: () => void;
  children: ReactNode;
  className?: string;
}) {
  return (
    <button
      type="button"
      className={`choice ${selected ? "selected" : ""} ${className}`}
      aria-pressed={selected}
      onClick={onClick}
    >
      {children}
      {selected && (
        <span className="check" aria-hidden="true">
          ✓
        </span>
      )}
    </button>
  );
}
export function Primary({
  children,
  onClick,
  disabled = false,
}: {
  children: ReactNode;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button className="primary" disabled={disabled} onClick={onClick}>
      {children}
    </button>
  );
}
export const dateLabel = (date: string) =>
  new Date(date + "T00:00:00Z").toLocaleDateString("ru-RU", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
