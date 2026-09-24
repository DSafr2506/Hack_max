import { describe, it, expect } from "vitest";
import { DEMO_EVENTS, DEMO_TODAY } from "../src/data/mock";
import { CITIES, GROUPS, SPECIAL } from "../src/data/catalog";
import {
  emptyFilters,
  filterEvents,
  profileFilters,
  changeTypes,
  validateFilters,
} from "../src/state/filters";
import { blankProfile, readProfile, saveProfile } from "../src/state/profile";
import type { Filters, Profile, Value } from "../src/types";
const p: Profile = {
  grade: 9,
  cityId: "moscow",
  types: ["olympiad", "hackathon"],
  goalText: "Любой текст",
  completed: true,
};
const run = (f: Filters) => filterEvents(DEMO_EVENTS, f, p, DEMO_TODAY);
describe("catalogue rules", () => {
  it("has unique cities and 4 events per type", () => {
    expect(new Set(CITIES.map((c) => c.id)).size).toBe(CITIES.length);
    for (const t of Object.keys(SPECIAL))
      expect(DEMO_EVENTS.filter((e) => e.type === t)).toHaveLength(4);
  });
  it("personalizes and ignores free text", () => {
    const f = profileFilters(p);
    const events = run(f);
    expect(events.length).toBeGreaterThan(0);
    expect(
      events.every(
        (e) =>
          p.types.includes(e.type) &&
          e.grades.includes(9) &&
          (e.eligibleRegions.includes("*") ||
            e.eligibleRegions.includes("Москва")),
      ),
    ).toBe(true);
    expect(
      filterEvents(
        DEMO_EVENTS,
        f,
        { ...p, goalText: "совсем другое" },
        DEMO_TODAY,
      ),
    ).toEqual(events);
  });
  it("combines OR within groups and AND between groups", () => {
    const f = emptyFilters();
    f.values = { grades: [8, 11], cost: ["Бесплатно", "Платно"] };
    expect(run(f)).toEqual(
      DEMO_EVENTS.filter(
        (e) =>
          (e.grades.includes(8) || e.grades.includes(11)) &&
          (e.cost === "Бесплатно" || e.cost === "Платно"),
      ),
    );
  });
  it("online is not nationwide eligibility", () => {
    const f = emptyFilters();
    f.values = { format: ["Онлайн"] };
    expect(run(f)).toHaveLength(8);
    f.regionOnly = true;
    expect(run(f)).toHaveLength(4);
  });
  it("soon requires open registration and inclusive 7-day window", () => {
    const f = { ...emptyFilters(), soon: true };
    const e = DEMO_EVENTS[0];
    const list = [
      { ...e, deadline: "2026-10-01" },
      { ...e, deadline: "2026-10-02" },
      { ...e, deadline: "2026-09-23" },
      { ...e, opens: "2026-09-25" },
    ];
    expect(filterEvents(list, f, p, DEMO_TODAY)).toEqual([list[0]]);
  });
  it("unknown boolean does not mean no", () => {
    const f = emptyFilters();
    f.values = { accessible: [false] };
    expect(run(f)).toHaveLength(4);
    expect(run(f).every((e) => e.accessible === false)).toBe(true);
  });
  it("all common categorical fields work", () => {
    for (const field of GROUPS.flatMap((g) => g.fields).filter(
      (f) => f.options || f.kind === "boolean",
    )) {
      for (const v of field.options ?? [true, false]) {
        const f = emptyFilters();
        f.values = { [field.key]: [v] };
        expect(run(f)).toEqual(
          DEMO_EVENTS.filter((e) => {
            const actual = (e as unknown as Record<string, Value | Value[]>)[
              field.key
            ];
            return Array.isArray(actual) ? actual.includes(v) : actual === v;
          }),
        );
      }
    }
  });
  it("all special fields filter their own type", () => {
    for (const type of Object.keys(SPECIAL) as (keyof typeof SPECIAL)[]) {
      const events = DEMO_EVENTS.filter((e) => e.type === type);
      for (const field of SPECIAL[type]) {
        const f = changeTypes(emptyFilters(), [type]);
        const value = (events[0].special as unknown as Record<string, Value>)[
          field.key
        ];
        if (field.kind === "number")
          f.specialRanges = {
            [field.key]: { min: String(value), max: String(value) },
          };
        else f.special = { [field.key]: [value] };
        expect(run(f)).toEqual(
          events.filter(
            (e) =>
              (e.special as unknown as Record<string, Value>)[field.key] ===
              value,
          ),
        );
      }
    }
  });
  it("drops incompatible special filters", () => {
    const f = {
      ...emptyFilters(),
      special: { subject: ["Физика"] },
      specialRanges: { teamSize: { min: "4" } },
    };
    expect(changeTypes(f, ["career"]).special).toEqual({});
    expect(changeTypes(f, ["career"]).specialRanges).toEqual({});
  });
  it("validates reversed, impossible and negative ranges", () => {
    for (const ranges of [
      { duration: { min: "5", max: "1" } },
      { duration: { min: "-1" } },
      { duration: { min: "1.5" } },
      { deadline: { min: "2026-02-30" } },
      { eventDates: { min: "2026-10-01", max: "2026-09-01" } },
    ] as Filters["ranges"][])
      expect(validateFilters({ ...emptyFilters(), ranges })).not.toBeNull();
  });
  it("filters dates by interval overlap and numeric inclusive bounds", () => {
    const f = emptyFilters();
    f.ranges = {
      eventDates: { min: "2026-10-25", max: "2026-10-26" },
      duration: { min: "7", max: "7" },
    };
    expect(run(f)).toHaveLength(4);
  });
});
describe("profile persistence", () => {
  it("round trips completed profile", () => {
    let raw = "";
    expect(
      saveProfile(
        {
          setItem: (_, v) => {
            raw = v;
          },
        },
        p,
      ),
    ).toBe(true);
    expect(readProfile({ getItem: () => raw })).toEqual(p);
  });
  it("recovers from corrupt or unavailable storage", () => {
    for (const raw of [
      "{",
      "null",
      JSON.stringify({ ...p, grade: 12 }),
      JSON.stringify({ ...p, cityId: "unknown" }),
      JSON.stringify({ ...p, types: ["toString"] }),
    ])
      expect(readProfile({ getItem: () => raw })).toEqual(blankProfile());
    expect(
      readProfile({
        getItem: () => {
          throw Error();
        },
      }),
    ).toEqual(blankProfile());
    expect(
      saveProfile(
        {
          setItem: () => {
            throw Error();
          },
        },
        p,
      ),
    ).toBe(false);
  });
  it("rejects incomplete completed profile", () => {
    expect(
      readProfile({ getItem: () => JSON.stringify({ ...p, types: [] }) }),
    ).toEqual(blankProfile());
  });
});
