import { describe, it, expect } from "vitest";
import { goalCodesFromText, toOpportunity, type BackendEvent } from "../src/services/api";

const base: BackendEvent = {
  id: 7,
  slug: "prod-spb",
  type: "hackathon",
  title: "Хакатон PROD",
  short_description: "кратко",
  description: "полное описание",
  organizer: "Олимпиада PROD",
  organizer_kind: "other",
  format: "offline",
  region_codes: ["78"],
  is_federal: false,
  venue_city: "Санкт-Петербург",
  grade_min: 8,
  grade_max: 10,
  participation: "team",
  registration_deadline: null,
  starts_at: "2026-10-16T07:00:00+00:00",
  ends_at: "2026-10-18T20:59:00+00:00",
  price_kind: "free",
  travel_covered: "no",
  accommodation_covered: "unknown",
  entry_kind: "open",
  selection_note: null,
  level: "regional",
  goal_codes: ["team", "skills"],
  subject_codes: ["informatics"],
  attributes: { tracks: ["backend", "frontend"], team_size_max: 5, has_mentors: true },
  freshness: "fresh",
  my_status: "going",
  trust: { source_url: "https://x.ru", source_name: "x.ru", verified_at: "2026-09-24T07:00:00+00:00", freshness: "fresh" },
  action: { go_url: "/go/7", has_external_registration: true, channel: "external" },
};

describe("маппинг бэкенд → фронт", () => {
  it("переводит поля и типы", () => {
    const o = toOpportunity(base, { informatics: "Информатика" })!;
    expect(o.type).toBe("hackathon");
    expect(o.grades).toEqual([8, 9, 10]);
    expect(o.format).toBe("Офлайн");
    expect(o.cost).toBe("Бесплатно");
    expect(o.participation).toBe("Команда");
    expect(o.travel).toBe(false);
    expect(o.accommodation).toBeUndefined();
    expect(o.goals).toEqual(["Команда и знакомства", "Навыки"]);
    expect(o.start).toBe("2026-10-16");
    expect(o.deadline).toBe("2026-10-16"); // без дедлайна — до начала
    expect(o.myStatus).toBe("going");
    expect(o.type === "hackathon" && o.special.teamSize).toBe(5);
  });
  it("смены camp → school, неизвестные типы отбрасываются", () => {
    expect(toOpportunity({ ...base, type: "camp" }, {})!.type).toBe("school");
    expect(toOpportunity({ ...base, type: "grant" }, {})).toBeNull();
  });
  it("доступность из региона как на бэкенде", () => {
    expect(toOpportunity({ ...base, format: "online" }, {})!.eligibleRegions).toEqual(["*"]);
    expect(
      toOpportunity({ ...base, is_federal: true, travel_covered: "yes" }, {})!.eligibleRegions,
    ).toEqual(["*"]);
    expect(toOpportunity(base, {})!.eligibleRegions).not.toContain("*");
  });
  it("цели из свободного текста", () => {
    expect(goalCodesFromText("Хочу поступить в МФТИ и найти команду")).toEqual(["admission", "team"]);
    expect(goalCodesFromText("")).toEqual([]);
  });
});
