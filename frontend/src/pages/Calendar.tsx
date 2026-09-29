import { useMemo, useState } from "react";
import type { Opportunity } from "../types";
import { BackArrow } from "../components/ui";
import { DateRangePicker } from "../components/DateRangePicker";
import { calendarMonths, datesInRange, firstOfMonth, lastOfMonth, monthsInRange, monthTitle, moveDate, moveMonth, parseCalendarDate } from "../state/calendar";
import type { CalendarMode, DateRange } from "../state/calendar";

type Entry = { title: string; color: string };
type Day = { label: string; entries: Entry[] };

const olympiad = { title: "Всероссийская олимпиада по искусственному интеллекту", color: "magenta" };
const ctf = { title: "InnoCTF Junior — турнир по кибербезопасности", color: "blue" };
const physics = { title: "Интернет-олимпиада школьников по физике: первый тур", color: "magenta" };
const belchonok = { title: "Университетская олимпиада «Бельчонок» по информатике", color: "magenta" };
const innopolis = { title: "Innopolis Open по математике: первый отборочный тур", color: "pink" };

const initialDays: Day[] = [
  { label: "15 Понедельник", entries: [olympiad, ctf, physics, belchonok] },
  { label: "16 Вторник", entries: [olympiad, ctf] },
  { label: "17 Среда", entries: [olympiad, ctf] },
  { label: "18 Четверг", entries: [olympiad, ctf] },
  { label: "19 Пятница", entries: [olympiad] },
  { label: "20 Суббота", entries: [olympiad] },
  { label: "21 Воскресенье", entries: [olympiad] },
];

const weekdayLabels = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"];
const monthlyEntries: Entry[][] = [
  [olympiad, ctf, physics, belchonok],
  [olympiad, ctf, innopolis],
  [olympiad, ctf, innopolis],
  [olympiad, ctf, innopolis],
  [olympiad, { title: "Национальная технологическая олимпиада (НТО)", color: "purple" }],
  [olympiad, { title: "Кубок CTF России", color: "blue" }],
  [olympiad, ctf],
];

export function Calendar({
  events,
  onBack,
  onOpen,
  mode,
  onChangeMode,
  ranges,
  onChangeRanges,
}: {
  events: Opportunity[];
  onBack: () => void;
  onOpen: (title: string) => void;
  mode: CalendarMode;
  onChangeMode: (mode: CalendarMode) => void;
  ranges: Record<CalendarMode, DateRange>;
  onChangeRanges: (ranges: Record<CalendarMode, DateRange>) => void;
}) {
  const [pickerOpen, setPickerOpen] = useState(false);
  const range = ranges[mode];
  const days = useMemo(() => datesInRange(range), [range]);
  const months = useMemo(() => monthsInRange(range), [range]);

  const openEntry = (entry: Entry) => {
    const match = events.find((event) =>
      event.title.toLocaleLowerCase("ru").includes(entry.title.toLocaleLowerCase("ru").slice(0, 12)),
    );
    if (match) onOpen(match.title);
    else onOpen(entry.title);
  };

  const weekStart = parseCalendarDate(range.start);
  const weekEnd = parseCalendarDate(range.end);
  const weekStartMonth = weekStart.getUTCMonth();
  const weekEndMonth = weekEnd.getUTCMonth();
  const sameYear = weekStart.getUTCFullYear() === weekEnd.getUTCFullYear();
  const weekLabel = range.start === range.end
    ? weekStart.getUTCDate() + " " + monthTitle(range.start)
    : weekStartMonth === weekEndMonth && sameYear
      ? weekStart.getUTCDate() + " – " + weekEnd.getUTCDate() + " " + calendarMonths[weekEndMonth] + ", " + weekEnd.getUTCFullYear()
      : weekStart.getUTCDate() + " " + calendarMonths[weekStartMonth] + (sameYear ? "" : " " + weekStart.getUTCFullYear()) + " – " + weekEnd.getUTCDate() + " " + calendarMonths[weekEndMonth] + " " + weekEnd.getUTCFullYear();
  const monthLabel = firstOfMonth(range.start) === firstOfMonth(range.end)
    ? monthTitle(range.start)
    : monthTitle(range.start) + " – " + monthTitle(range.end);

  function movePeriod(direction: number) {
    const next = mode === "week"
      ? { start: moveDate(range.start, direction * 7), end: moveDate(range.end, direction * 7) }
      : { start: moveMonth(range.start, direction), end: moveMonth(range.end, direction, true) };
    onChangeRanges({ week: next, months: next });
  }

  const eventColors = { olympiad: "magenta", hackathon: "blue", career: "pink", school: "purple" };
  function entriesForPeriod(start: string, end: string): Entry[] {
    return events.filter((event) => event.start <= end && event.end >= start)
      .filter((event, index, matching) => matching.findIndex((item) => item.title === event.title) === index)
      .map((event) => ({ title: event.title, color: eventColors[event.type] }));
  }
  function entriesForDay(date: string) {
    const referenceIndex = initialDays.findIndex((_, index) => date === moveDate("2026-09-15", index));
    return referenceIndex >= 0 ? initialDays[referenceIndex].entries : entriesForPeriod(date, date);
  }
  function entriesForMonth(month: string) {
    const referenceIndex = parseCalendarDate(month).getUTCMonth();
    if (month.startsWith("2026-") && referenceIndex < monthlyEntries.length) return monthlyEntries[referenceIndex];
    return entriesForPeriod(range.start > month ? range.start : month, range.end < lastOfMonth(month) ? range.end : lastOfMonth(month));
  }

  const renderEntries = (entries: Entry[]) => entries.length ? entries.map((entry) => (
    <button className="calendar-event" key={entry.title} onClick={() => openEntry(entry)}>
      <i className={"event-dot " + entry.color} aria-hidden="true" />
      <span>{entry.title}</span>
    </button>
  )) : <span className="calendar-empty-day">Нет мероприятий</span>;

  return (
    <main className="calendar-page">
      <div className="calendar-toolbar">
        <button className="calendar-back" aria-label="Назад" onClick={onBack}><BackArrow className="figma-back-arrow" /></button>
        <div className="calendar-switch" aria-label="Режим календаря">
          <button className={mode === "week" ? "active" : ""} aria-pressed={mode === "week"} onClick={() => onChangeMode("week")}>По неделям</button>
          <button className={mode === "months" ? "active" : ""} aria-pressed={mode === "months"} onClick={() => onChangeMode("months")}>По месяцам</button>
        </div>
      </div>
      <div className="calendar-range">
        <button aria-label="Предыдущий период" onClick={() => movePeriod(-1)}>‹</button>
        <button aria-label="Следующий период" onClick={() => movePeriod(1)}>›</button>
        <strong>{mode === "week" ? weekLabel : monthLabel}</strong>
        <button className="calendar-icon" aria-label="Выбрать даты" aria-haspopup="dialog" aria-expanded={pickerOpen} onClick={() => setPickerOpen(true)}>
          <span className="calendar-trigger-glyph" aria-hidden="true"><img src={pickerOpen ? "/assets/figma/calendar-picker-active.svg" : "/assets/figma/calendar-picker.svg"} width="46" height="46" alt="" /></span>
        </button>
      </div>
      <div className="calendar-list">
        {mode === "week"
          ? days.map((value) => {
              const date = parseCalendarDate(value);
              const label = date.getUTCDate() + " " + weekdayLabels[(date.getUTCDay() + 6) % 7];
              return (
                <section className="calendar-day" key={value}>
                  <h2>{label}</h2>
                  <div className="calendar-events">
                    {renderEntries(entriesForDay(value))}
                  </div>
                </section>
              );
            })
          : months.map((month) => (
              <section className="calendar-day" key={month}>
                <h2>{monthTitle(month)}</h2>
                <div className="calendar-events">
                  {renderEntries(entriesForMonth(month))}
                </div>
              </section>
            ))}
      </div>
      {pickerOpen && <DateRangePicker range={range} onClose={() => setPickerOpen(false)} onApply={(next) => { onChangeRanges({ week: next, months: next }); setPickerOpen(false); }} />}
    </main>
  );
}
