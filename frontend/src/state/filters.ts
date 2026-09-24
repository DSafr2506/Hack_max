import type { Filters, Opportunity, Profile, Value } from "../types";
import { CITIES } from "../data/catalog";
export const emptyFilters = (): Filters => ({
  types: [],
  goals: [],
  values: {},
  ranges: {},
  regionOnly: false,
  soon: false,
  special: {},
  specialRanges: {},
});
export const profileFilters = (p: Profile): Filters => ({
  ...emptyFilters(),
  types: [...p.types],
  values: p.grade ? { grades: [p.grade] } : {},
  regionOnly: !!CITIES.find((c) => c.id === p.cityId),
});
export const changeTypes = (f: Filters, types: Filters["types"]): Filters => ({
  ...f,
  types,
  special: {},
  specialRanges: {},
});
const day = (s: string) => Date.parse(s + "T00:00:00Z");
function matches(record: object, values: Record<string, Value[]>) {
  return Object.entries(values).every(([key, selected]) => {
    if (!selected.length) return true;
    const actual = (record as Record<string, unknown>)[key];
    return selected.some((v) =>
      Array.isArray(actual) ? actual.includes(v) : actual === v,
    );
  });
}
function rangesMatch(record: object, ranges: Filters["ranges"]) {
  return Object.entries(ranges).every(([key, r]) => {
    if (!r.min && !r.max) return true;
    const obj = record as Record<string, unknown>;
    if (key === "eventDates")
      return (
        (!r.min || String(obj.end) >= r.min) &&
        (!r.max || String(obj.start) <= r.max)
      );
    const value = obj[key];
    if (value === undefined) return false;
    const numeric = typeof value === "number";
    return (
      (!r.min || (numeric ? value >= Number(r.min) : String(value) >= r.min)) &&
      (!r.max || (numeric ? value <= Number(r.max) : String(value) <= r.max))
    );
  });
}
export function validateFilters(f: Filters): string | null {
  for (const [key, r] of Object.entries({ ...f.ranges, ...f.specialRanges })) {
    const date = ["deadline", "eventDates"].includes(key);
    for (const v of [r.min, r.max])
      if (
        v &&
        (date
          ? !/^\d{4}-\d{2}-\d{2}$/.test(v) ||
            !Number.isFinite(day(v)) ||
            new Date(day(v)).toISOString().slice(0, 10) !== v
          : !Number.isFinite(Number(v)) ||
            Number(v) < 0 ||
            !Number.isInteger(Number(v)))
      )
        return "Укажите корректные даты и целые неотрицательные значения.";
    if (
      r.min &&
      r.max &&
      (date ? r.min > r.max : Number(r.min) > Number(r.max))
    )
      return "Начало диапазона не может быть больше конца.";
  }
  return null;
}
export function filterEvents(
  events: Opportunity[],
  f: Filters,
  p: Profile,
  today: string,
) {
  if (validateFilters(f)) return [];
  const region = CITIES.find((c) => c.id === p.cityId)?.region;
  return events.filter(
    (e) =>
      (!f.types.length || f.types.includes(e.type)) &&
      (!f.goals.length || f.goals.some((g) => e.goals.includes(g))) &&
      (!f.regionOnly ||
        (!!region &&
          (e.eligibleRegions.includes("*") ||
            e.eligibleRegions.includes(region)))) &&
      (!f.soon ||
        (e.opens <= today &&
          e.deadline >= today &&
          day(e.deadline) - day(today) <= 7 * 86400000)) &&
      matches(e, f.values) &&
      rangesMatch(e, f.ranges) &&
      (f.types.length !== 1 ||
        (matches(e.special, f.special) &&
          rangesMatch(e.special, f.specialRanges))),
  );
}
export const toggle = <T>(values: T[], v: T) =>
  values.includes(v) ? values.filter((x) => x !== v) : [...values, v];
