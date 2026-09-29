import type { ReactNode } from "react";

export function BackArrow({ className = "" }: { className?: string }) {
  return (
    <svg className={className} viewBox="40 0 38 42" aria-hidden="true" focusable="false">
      <path d="M42 21H76" stroke="#5249F4" strokeWidth="4" strokeLinecap="round" />
      <path d="M42 21L55.5 37" stroke="#5249F4" strokeWidth="4" />
      <path d="M42 21L55.5 5" stroke="#5249F4" strokeWidth="4" />
    </svg>
  );
}

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
  ariaLabel,
}: {
  children: ReactNode;
  onClick: () => void;
  disabled?: boolean;
  ariaLabel?: string;
}) {
  return (
    <button className="primary" aria-label={ariaLabel} disabled={disabled} onClick={onClick}>
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
