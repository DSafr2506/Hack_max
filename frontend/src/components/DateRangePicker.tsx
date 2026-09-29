import { useEffect, useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import { calendarDate, firstOfMonth, lastOfMonth, monthTitle, moveDate, moveMonth, orderedRange, parseCalendarDate } from "../state/calendar";
import type { DateRange } from "../state/calendar";

const weekdays = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];
const dateName = (value: string) => parseCalendarDate(value).toLocaleDateString("ru-RU", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });

export function DateRangePicker({ range, onClose, onApply }: {
  range: DateRange;
  onClose: () => void;
  onApply: (range: DateRange) => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [month, setMonth] = useState(() => firstOfMonth(range.start));
  const [draft, setDraft] = useState(range);
  const [anchor, setAnchor] = useState<string | null>(null);
  const [hovered, setHovered] = useState<string | null>(null);
  const [focusDate, setFocusDate] = useState<string | null>(null);
  const highlighted = anchor && hovered ? orderedRange(anchor, hovered) : draft;
  const monthDate = parseCalendarDate(month);
  const offset = (monthDate.getUTCDay() + 6) % 7;
  const dayCount = parseCalendarDate(lastOfMonth(month)).getUTCDate();
  const slots = Math.ceil((offset + dayCount) / 7) * 7;

  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const el = dialog.current!;
    const overflow = document.body.style.overflow;
    el.showModal();
    document.body.style.overflow = "hidden";
    el.querySelector<HTMLButtonElement>(`[data-date="${range.start}"]`)?.focus();
    return () => {
      el.close();
      document.body.style.overflow = overflow;
      previous?.focus();
    };
  }, [range.start]);

  useEffect(() => {
    if (focusDate) dialog.current?.querySelector<HTMLButtonElement>(`[data-date="${focusDate}"]`)?.focus();
  }, [focusDate, month]);

  function selectDate(date: string) {
    setHovered(null);
    if (anchor) {
      setDraft(orderedRange(anchor, date));
      setAnchor(null);
    } else {
      setDraft({ start: date, end: date });
      setAnchor(date);
    }
  }

  function moveFocus(event: KeyboardEvent<HTMLButtonElement>, date: string) {
    const shifts: Record<string, number> = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7 };
    let next: string;
    if (event.key in shifts) next = moveDate(date, shifts[event.key]);
    else if (event.key === "PageUp" || event.key === "PageDown") next = moveMonth(date, event.key === "PageUp" ? -1 : 1);
    else if (event.key === "Home" || event.key === "End") {
      const weekday = (parseCalendarDate(date).getUTCDay() + 6) % 7;
      next = moveDate(date, event.key === "Home" ? -weekday : 6 - weekday);
    } else return;
    event.preventDefault();
    setMonth(firstOfMonth(next));
    setFocusDate(next);
  }

  return (
    <dialog ref={dialog} className="calendar-date-dialog" aria-label="Выбор дат"
      onCancel={(event) => { event.preventDefault(); onClose(); }}
      onClick={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <div className="calendar-picker-content">
        <header className="calendar-picker-header">
          <h2>{monthTitle(month)}</h2>
          <div className="calendar-picker-month-controls">
            <button type="button" aria-label="Предыдущий месяц" onClick={() => { setMonth(moveMonth(month, -1)); setHovered(null); }}><svg viewBox="0 0 16 16" aria-hidden="true"><path d="m10 3-5 5 5 5" /></svg></button>
            <button type="button" aria-label="Следующий месяц" onClick={() => { setMonth(moveMonth(month, 1)); setHovered(null); }}><svg viewBox="0 0 16 16" aria-hidden="true"><path d="m6 3 5 5-5 5" /></svg></button>
          </div>
        </header>
        <div className="calendar-picker-weekdays" aria-hidden="true">
          {weekdays.map((day, index) => <span className={index > 4 ? "is-weekend" : ""} key={day}>{day}</span>)}
        </div>
        <div className="calendar-picker-days" onMouseLeave={() => setHovered(null)}>
          {Array.from({ length: slots }, (_, index) => {
            const day = index - offset + 1;
            if (day < 1 || day > dayCount) return <span key={index} aria-hidden="true" />;
            const date = calendarDate(new Date(Date.UTC(monthDate.getUTCFullYear(), monthDate.getUTCMonth(), day)));
            const inRange = date >= highlighted.start && date <= highlighted.end;
            const start = date === highlighted.start;
            const end = date === highlighted.end;
            const classes = ["calendar-picker-cell", index % 7 > 4 ? "is-weekend" : "", inRange ? "is-in-range" : "", start ? "is-range-start" : "", end ? "is-range-end" : ""].filter(Boolean).join(" ");
            return <span className={classes} key={date}>
              <button type="button" data-date={date} aria-label={dateName(date)} aria-pressed={date >= draft.start && date <= draft.end}
                onClick={() => selectDate(date)} onMouseEnter={() => { if (anchor) setHovered(date); }} onKeyDown={(event) => moveFocus(event, date)}>{day}</button>
            </span>;
          })}
        </div>
        <p className="calendar-picker-hint">{anchor ? "Выберите конечную дату или примените один день" : "Выберите начальную и конечную даты"}</p>
        <p className="calendar-picker-selection" role="status">{dateName(draft.start)}{draft.start !== draft.end && <> — {dateName(draft.end)}</>}</p>
        <footer className="calendar-picker-actions">
          <button type="button" onClick={onClose}>Отмена</button>
          <button type="button" className="calendar-picker-apply" onClick={() => onApply(draft)}>Применить</button>
        </footer>
      </div>
    </dialog>
  );
}
