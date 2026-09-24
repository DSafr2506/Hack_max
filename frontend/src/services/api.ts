// HTTP-клиент бэкенда и перевод его модели в модель фронта (types.ts).
// Бэкенд и фронт живут на одном домене (в Docker их связывает Caddy),
// поэтому пути относительные.

import type { EventType, Opportunity, Profile } from "../types";
import { GOALS } from "../data/catalog";

// ─── модель бэкенда ───

type Code = { code: string; name: string };
export type BackendDicts = {
  type: Code[];
  goal: Code[];
  subject: Code[];
  region: (Code & { tz: string })[];
  city: { name: string; region_code: string }[];
};

export type BackendUser = {
  id: number;
  region_code: string | null;
  city: string | null;
  grade: number | null;
  type_codes: string[];
  goal_codes: string[];
  notifications_enabled: boolean;
  onboarded: boolean;
};

export type BackendEvent = {
  id: number;
  slug: string;
  type: string;
  title: string;
  short_description: string;
  description: string;
  organizer: string;
  organizer_kind: string;
  format: "online" | "offline" | "hybrid";
  region_codes: string[];
  is_federal: boolean;
  venue_city: string | null;
  grade_min: number | null;
  grade_max: number | null;
  participation: string;
  registration_deadline: string | null;
  starts_at: string | null;
  ends_at: string | null;
  price_kind: string;
  travel_covered: string;
  accommodation_covered: string;
  entry_kind: string;
  selection_note: string | null;
  level: string | null;
  goal_codes: string[];
  subject_codes: string[];
  attributes: Record<string, unknown>;
  freshness: string;
  my_status: string | null;
  trust: {
    source_url: string;
    source_name: string;
    verified_at: string | null;
    freshness: string;
  };
  action: { go_url: string; has_external_registration: boolean; channel: string };
};

export type CalendarItem = {
  event_id: number;
  slug: string;
  kind: "deadline" | "start";
  at: string;
  title: string;
};

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
  }
}

// ─── транспорт ───

let token: string | null = null;
export const hasSession = () => token !== null;
export const sessionToken = () => token;

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  signal?: AbortSignal,
): Promise<T> {
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(path, {
    method,
    headers,
    signal,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) {
    let code = "error";
    let message = res.statusText;
    try {
      const data = await res.json();
      code = data?.error?.code ?? code;
      message = data?.error?.message ?? message;
    } catch {
      /* не JSON */
    }
    throw new ApiError(res.status, code, message);
  }
  return (await res.json()) as T;
}

export const api = {
  async launch(body: { init_data?: string; dev_user_id?: string }) {
    const r = await request<{
      token: string;
      user: BackendUser;
      is_new: boolean;
      start_param: string | null;
    }>("POST", "/api/auth/launch", body);
    token = r.token;
    return r;
  },
  dicts: () => request<BackendDicts>("GET", "/api/dicts"),
  events: (signal?: AbortSignal) =>
    request<{ items: BackendEvent[]; total: number }>(
      "GET",
      "/api/events?detail=full&limit=200&sort=deadline",
      undefined,
      signal,
    ),
  eventById: (id: number) => request<BackendEvent>("GET", `/api/events/by-id/${id}`),
  onboarding: (body: {
    grade: number | null;
    city: string;
    type_codes: string[];
    goal_codes: string[];
  }) => request<BackendUser>("POST", "/api/me/onboarding", body),
  participate: (eventId: number, status: "going" | "skipped") =>
    request<{ id: number; status: string }>("POST", "/api/me/participations", {
      event_id: eventId,
      status,
    }),
  calendar: () => request<CalendarItem[]>("GET", "/api/me/calendar"),
  share: (slug: string) =>
    request<{ deep_link: string; share_url: string; share_text: string }>(
      "GET",
      `/api/events/${encodeURIComponent(slug)}/share`,
    ),
  shareOpen: (tok: string) =>
    request<{ kind: string; ref_id: number }>("POST", `/api/share/${tok}/open`),
  demoReminder: (eventId: number) =>
    request<{ reminder_id: number }>("POST", "/api/demo/fire-reminder", {
      event_id: eventId,
      delay_seconds: 0,
    }),
};

export const absolute = (path: string) => new URL(path, location.origin).toString();

// ─── справочники: коды бэкенда ↔ подписи фронта ───

/** Типы фронта ↔ типы бэкенда. «school» во фронте — это «camp» (смены) на бэкенде. */
export const TYPE_TO_BACKEND: Record<EventType, string> = {
  olympiad: "olympiad",
  school: "camp",
  hackathon: "hackathon",
  career: "career",
};
const TYPE_FROM_BACKEND: Record<string, EventType> = {
  olympiad: "olympiad",
  camp: "school",
  hackathon: "hackathon",
  career: "career",
};

/** Цели фронта (GOALS, по порядку) ↔ коды бэкенда. */
const GOAL_CODES = ["admission", "money", "free_trip", "career", "portfolio", "skills", "team"];
const goalLabel = (code: string) => GOALS[GOAL_CODES.indexOf(code)];

/**
 * Цели на последнем шаге онбординга пишутся свободным текстом (как в макете).
 * Сам текст на сервер не отправляем — только коды целей, найденные по ключевым словам.
 */
const GOAL_KEYWORDS: [string, RegExp][] = [
  ["admission", /поступ|вуз|бви|льгот|универ|институт|егэ/i],
  ["money", /деньг|приз|грант|стипенд|заработ|выигр/i],
  ["free_trip", /поезд|путешеств|лагер|смен|сириус|артек|бесплатн/i],
  ["career", /работ|професс|карьер|стажир|профори/i],
  ["portfolio", /портфол|диплом|достижен|грамот/i],
  ["skills", /навык|научит|освоит|программир|изучит|разобрат|попробов/i],
  ["team", /команд|друз|знаком|единомышл|общени/i],
];
export function goalCodesFromText(text: string): string[] {
  return GOAL_KEYWORDS.filter(([, re]) => re.test(text)).map(([code]) => code);
}

let regionNames: Record<string, string> = {};
export function setRegionNames(dicts: BackendDicts) {
  regionNames = Object.fromEntries(dicts.region.map((r) => [r.code, r.name]));
}
const regionName = (code: string) => regionNames[code] ?? code;

const SUBJECT_DIRECTION: [string, RegExp][] = [
  ["Технологии", /informatics|ai|engineering|robotics|security/],
  ["Наука", /math|physics|chemistry|biology|ecology|geography|astronomy|medicine/],
  ["Творчество", /art|media|literature/],
  ["Общество", /social|law|economics|history|business|russian|english/],
];
const directionOf = (subjects: string[]) =>
  SUBJECT_DIRECTION.find(([, re]) => subjects.some((s) => re.test(s)))?.[0] ?? "Наука";

const FORMAT: Record<string, string> = { online: "Онлайн", offline: "Офлайн", hybrid: "Гибрид" };
const COST: Record<string, string> = {
  free: "Бесплатно",
  paid: "Платно",
  quota: "По квоте",
  unknown: "Не указано",
};
const ADMISSION: Record<string, string> = {
  open: "Открытая регистрация",
  selection: "Конкурсный отбор",
  by_result: "По итогам другого события",
  invite_only: "По приглашению",
};
const LEVEL: Record<string, string> = {
  school: "Школьный",
  municipal: "Муниципальный",
  regional: "Региональный",
  federal: "Всероссийский",
  international: "Международный",
};
const ORG: Record<string, string> = {
  gov: "Государственная организация",
  university: "Вуз",
  company: "Компания",
  ngo: "НКО",
  other: "Другое",
};
const PARTICIPATION: Record<string, string> = {
  individual: "Один",
  team: "Команда",
  both: "Один или команда",
};
const OLYMPIAD_STATUS: Record<string, string> = {
  vsosh: "ВсОШ",
  rsosh_1: "РСОШ I",
  rsosh_2: "РСОШ II",
  rsosh_3: "РСОШ III",
  other: "Прочие",
};
const CAREER_KIND: Record<string, string> = {
  excursion: "Экскурсия",
  job_trial: "Профпроба",
  internship: "Стажировка",
  targeted: "Целевое обучение",
};
const SEASONS = ["Зима", "Зима", "Весна", "Весна", "Весна", "Лето", "Лето", "Лето", "Осень", "Осень", "Осень", "Зима"];

const covered = (v: string): boolean | undefined =>
  v === "yes" || v === "partial" ? true : v === "no" ? false : undefined;

/** Дата YYYY-MM-DD по Москве — в этом формате фронт сравнивает даты. */
export function mskDate(iso: string | Date): string {
  const d = typeof iso === "string" ? new Date(iso) : iso;
  return new Date(d.getTime() + 3 * 3600_000).toISOString().slice(0, 10);
}

const str = (v: unknown): string | undefined => (typeof v === "string" && v ? v : undefined);
const num = (v: unknown): number | undefined => (typeof v === "number" ? v : undefined);
const bool = (v: unknown): boolean | undefined => (typeof v === "boolean" ? v : undefined);

/** Мероприятие бэкенда → Opportunity фронта. Типы, которых нет во фронте, отбрасываются. */
export function toOpportunity(e: BackendEvent, subjectNames: Record<string, string>): Opportunity | null {
  const type = TYPE_FROM_BACKEND[e.type];
  if (!type) return null;
  const a = e.attributes ?? {};

  const deadlineIso = e.registration_deadline ?? e.starts_at ?? e.ends_at;
  const deadline = deadlineIso ? mskDate(deadlineIso) : "2099-12-31";
  const start = e.starts_at ? mskDate(e.starts_at) : deadline;
  const end = e.ends_at ? mskDate(e.ends_at) : start;
  const duration = Math.max(1, Math.round((Date.parse(end) - Date.parse(start)) / 86_400_000) + 1);

  // «Доступно из моего региона» — как на бэкенде: онлайн, свой регион или федеральное с оплатой проезда
  const travel = covered(e.travel_covered);
  const anywhere = e.format !== "offline" || (e.is_federal && travel === true);
  const eligibleRegions = anywhere ? ["*"] : e.region_codes.map(regionName);

  const gmin = e.grade_min ?? 8;
  const gmax = e.grade_max ?? 11;
  const grades = ([8, 9, 10, 11] as const).filter((g) => g >= gmin && g <= gmax);

  const goals = e.goal_codes.map(goalLabel).filter(Boolean);
  const direction = directionOf(e.subject_codes);
  const subject = subjectNames[e.subject_codes[0]] ?? "Не указано";

  const common = {
    id: String(e.id),
    backendId: e.id,
    slug: e.slug,
    title: e.title,
    description: e.description || e.short_description,
    organizer: e.organizer,
    format: FORMAT[e.format] ?? e.format,
    region:
      e.venue_city ??
      (e.format === "online" ? "Онлайн" : e.region_codes.length ? e.region_codes.map(regionName).join(", ") : "Россия"),
    eligibleRegions,
    grades: grades.length ? [...grades] : [8, 9, 10, 11],
    goals,
    results: goals,
    opens: "2000-01-01",
    deadline,
    start,
    end,
    duration,
    cost: COST[e.price_kind] ?? "Не указано",
    price: 0,
    participation: PARTICIPATION[e.participation] ?? "Один",
    travel,
    accommodation: covered(e.accommodation_covered),
    admission: ADMISSION[e.entry_kind] ?? "Открытая регистрация",
    level: LEVEL[e.level ?? ""] ?? "Не указано",
    organizerType: ORG[e.organizer_kind] ?? "Другое",
    direction,
    verified: Boolean(e.trust.verified_at) && e.trust.freshness === "fresh",
    source: e.trust.source_url,
    sourceName: e.trust.source_name,
    verifiedAt: e.trust.verified_at,
    freshness: e.trust.freshness,
    hasRegistration: e.action.has_external_registration,
    registrationChannel: e.action.channel,
    goUrl: e.action.go_url,
    myStatus: e.my_status,
    selectionNote: e.selection_note,
    benefitNote: str(a.benefit_note),
    hasDeadline: Boolean(e.registration_deadline),
  } as const;

  const grades8 = common.grades as Opportunity["grades"];
  switch (type) {
    case "olympiad":
      return {
        ...common,
        grades: grades8,
        type,
        special: {
          status: OLYMPIAD_STATUS[str(a.olympiad_status) ?? "other"] ?? "Прочие",
          subject,
          stage: str(a.stage) === "school" ? "Школьный" : (str(a.stage) ?? "Отборочный"),
          onlineSelection: bool(a.has_online_qualifier),
          university: e.organizer_kind === "university" ? e.organizer : "Вуз не указан",
          benefit: str(a.benefit_note) ? "Указано организатором" : "Не указано",
        },
      };
    case "school":
      return {
        ...common,
        grades: grades8,
        type,
        special: {
          schoolDirection: direction,
          selection: str(a.selection_method) ?? common.admission,
          quotaRegion: a.has_region_quota ? e.region_codes.map(regionName).join(", ") || "Есть квота" : "Нет квоты",
          season: str(a.season)
            ? str(a.season)!.charAt(0).toUpperCase() + str(a.season)!.slice(1)
            : SEASONS[new Date(start).getUTCMonth()],
          achievements: bool(a.required_achievements),
        },
      };
    case "hackathon":
      return {
        ...common,
        grades: grades8,
        type,
        special: {
          stack: Array.isArray(a.tracks) && a.tracks.length ? (a.tracks as string[]).join(", ") : subject,
          teamSize: num(a.team_size_max),
          teamSearch: undefined,
          experience: str(a.difficulty) ?? "Не указано",
          prizeFund: num(a.prize_fund),
          mentors: bool(a.has_mentors),
        },
      };
    case "career":
      return {
        ...common,
        grades: grades8,
        type,
        special: {
          industry: str(a.industry) ?? direction,
          company: str(a.company) ?? e.organizer,
          activity: CAREER_KIND[str(a.program_kind) ?? ""] ?? "Не указано",
          targeted: bool(a.leads_to_targeted),
          minAge: num(a.safety_age_min),
          transfer: bool(a.transfer_provided),
        },
      };
  }
}

/** Профиль бэкенда → профиль фронта (для входа с другого устройства). */
export function profileFromBackend(u: BackendUser, local: Profile): Profile | null {
  if (!u.onboarded || !u.city || !u.grade) return null;
  const types = u.type_codes.map((c) => TYPE_FROM_BACKEND[c]).filter(Boolean) as EventType[];
  if (!types.length) return null;
  return {
    grade: u.grade as Profile["grade"],
    cityId: u.city,
    types,
    goalText: local.goalText,
    completed: true,
  };
}
