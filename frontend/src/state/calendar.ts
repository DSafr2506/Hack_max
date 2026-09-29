export type DateRange = { start: string; end: string };
export type CalendarMode = "week" | "months";

export const initialCalendarRanges = (): Record<CalendarMode, DateRange> => ({
  week: { start: "2026-09-15", end: "2026-09-21" },
  months: { start: "2026-01-01", end: "2026-06-30" },
});

export const calendarMonths = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"];

export const parseCalendarDate = (value: string) => new Date(value + "T00:00:00Z");
export const calendarDate = (value: Date) => value.toISOString().slice(0, 10);

export function moveDate(value: string, days: number) {
  const date = parseCalendarDate(value);
  date.setUTCDate(date.getUTCDate() + days);
  return calendarDate(date);
}

export function moveMonth(value: string, months: number, preserveMonthEnd = false) {
  const date = parseCalendarDate(value);
  const day = date.getUTCDate();
  const wasMonthEnd = day === new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth() + 1, 0)).getUTCDate();
  const target = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth() + months, 1));
  const lastDay = new Date(Date.UTC(target.getUTCFullYear(), target.getUTCMonth() + 1, 0)).getUTCDate();
  target.setUTCDate(preserveMonthEnd && wasMonthEnd ? lastDay : Math.min(day, lastDay));
  return calendarDate(target);
}

export function firstOfMonth(value: string) {
  const date = parseCalendarDate(value);
  return calendarDate(new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), 1)));
}

export function lastOfMonth(value: string) {
  const date = parseCalendarDate(value);
  return calendarDate(new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth() + 1, 0)));
}

export function orderedRange(first: string, second: string): DateRange {
  return first <= second ? { start: first, end: second } : { start: second, end: first };
}

export function datesInRange({ start, end }: DateRange) {
  const dates: string[] = [];
  for (let date = start; date <= end; date = moveDate(date, 1)) dates.push(date);
  return dates;
}

export function monthsInRange({ start, end }: DateRange) {
  const months: string[] = [];
  for (let month = firstOfMonth(start); month <= end; month = moveMonth(month, 1)) months.push(month);
  return months;
}

export function monthTitle(value: string) {
  const date = parseCalendarDate(value);
  return calendarMonths[date.getUTCMonth()] + " " + date.getUTCFullYear();
}
