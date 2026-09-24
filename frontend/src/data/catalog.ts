import type { City, EventType, Field } from "../types";
export const TYPES: Record<EventType, string> = {
  olympiad: "Олимпиады",
  school: "Образовательные смены",
  hackathon: "Хакатоны",
  career: "Профориентация",
};
export const GOALS = [
  "Льготы при поступлении",
  "Деньги: грант, приз, стипендия",
  "Бесплатная поездка / смена",
  "Работа и профессия",
  "Портфолио, диплом",
  "Навыки",
  "Команда и знакомства",
];
export const REGIONS = [
  "Москва",
  "Санкт-Петербург",
  "Республика Татарстан",
  "Краснодарский край",
  "Республика Хакасия",
  "Республика Башкортостан",
  "Новосибирская область",
];
export const CITIES: City[] = [
  { id: "abaza", name: "Абаза", region: REGIONS[4] },
  { id: "abakan", name: "Абакан", region: REGIONS[4] },
  { id: "abinsk", name: "Абинск", region: REGIONS[3] },
  { id: "agidel", name: "Агидель", region: REGIONS[5] },
  { id: "kazan", name: "Казань", region: REGIONS[2] },
  { id: "krasnodar", name: "Краснодар", region: REGIONS[3] },
  { id: "moscow", name: "Москва", region: REGIONS[0] },
  { id: "novosibirsk", name: "Новосибирск", region: REGIONS[6] },
  { id: "spb", name: "Санкт-Петербург", region: REGIONS[1] },
];
export const GROUPS: { label: string; fields: Field[] }[] = [
  {
    label: "Где",
    fields: [
      { key: "region", label: "Регион проведения", options: REGIONS },
      {
        key: "format",
        label: "Формат",
        options: ["Онлайн", "Офлайн", "Гибрид"],
      },
    ],
  },
  {
    label: "Кто может участвовать",
    fields: [
      { key: "grades", label: "Класс", options: [8, 9, 10, 11] },
      { key: "participation", label: "Участие", options: ["Один", "Команда"] },
      { key: "accessible", label: "Доступно для ОВЗ", kind: "boolean" },
      {
        key: "parentalConsent",
        label: "Требуется согласие родителей",
        kind: "boolean",
      },
    ],
  },
  {
    label: "Когда",
    fields: [
      { key: "deadline", label: "Дедлайн заявки", kind: "date" },
      {
        key: "eventDates",
        label: "Даты проведения (пересечение периода)",
        kind: "date",
      },
      { key: "duration", label: "Длительность, дней", kind: "number" },
    ],
  },
  {
    label: "Стоимость",
    fields: [
      {
        key: "cost",
        label: "Стоимость",
        options: ["Бесплатно", "Платно", "По квоте"],
      },
      { key: "travel", label: "Оплачивается проезд", kind: "boolean" },
      {
        key: "accommodation",
        label: "Оплачивается проживание",
        kind: "boolean",
      },
    ],
  },
  {
    label: "Как попасть",
    fields: [
      {
        key: "admission",
        label: "Способ поступления",
        options: [
          "Открытая регистрация",
          "Конкурсный отбор",
          "По итогам другого события",
          "По приглашению",
        ],
      },
    ],
  },
  {
    label: "Дополнительно",
    fields: [
      {
        key: "level",
        label: "Уровень",
        options: [
          "Школьный",
          "Муниципальный",
          "Региональный",
          "Всероссийский",
          "Международный",
        ],
      },
      {
        key: "organizerType",
        label: "Тип организатора",
        options: ["Государственная организация", "Вуз", "Компания", "НКО"],
      },
      {
        key: "direction",
        label: "Направление",
        options: ["Наука", "Технологии", "Творчество", "Общество"],
      },
      { key: "verified", label: "Проверено платформой", kind: "boolean" },
    ],
  },
];
export const SPECIAL: Record<EventType, Field[]> = {
  olympiad: [
    {
      key: "status",
      label: "Статус",
      options: ["ВсОШ", "РСОШ I", "РСОШ II", "РСОШ III", "Прочие"],
    },
    {
      key: "subject",
      label: "Предмет",
      options: ["Математика", "Информатика", "Физика", "Литература"],
    },
    {
      key: "stage",
      label: "Этап",
      options: ["Школьный", "Отборочный", "Региональный", "Заключительный"],
    },
    { key: "onlineSelection", label: "Онлайн-отбор", kind: "boolean" },
    {
      key: "university",
      label: "Вуз-организатор",
      options: [
        "Северный университет",
        "Университет «Вектор»",
        "Вуз не указан",
      ],
    },
    {
      key: "benefit",
      label: "Тип льготы",
      options: ["БВИ", "100 баллов", "Дополнительные баллы", "Без льгот"],
    },
  ],
  school: [
    {
      key: "schoolDirection",
      label: "Направление смены",
      options: ["Наука", "Технологии", "Творчество", "Общество"],
    },
    {
      key: "selection",
      label: "Способ отбора",
      options: [
        "Портфолио",
        "Тестирование",
        "Мотивационное письмо",
        "Без отбора",
      ],
    },
    {
      key: "quotaRegion",
      label: "Квота региона",
      options: [...REGIONS, "Нет квоты"],
    },
    {
      key: "season",
      label: "Сезон",
      options: ["Весна", "Лето", "Осень", "Зима"],
    },
    { key: "achievements", label: "Требуются достижения", kind: "boolean" },
  ],
  hackathon: [
    {
      key: "stack",
      label: "Трек / стек",
      options: ["Web / React", "Python / AI", "Робототехника", "Дизайн"],
    },
    { key: "teamSize", label: "Размер команды, человек", kind: "number" },
    { key: "teamSearch", label: "Есть поиск команды", kind: "boolean" },
    {
      key: "experience",
      label: "Уровень подготовки",
      options: ["Начальный", "Средний", "Продвинутый"],
    },
    { key: "prizeFund", label: "Призовой фонд, ₽", kind: "number" },
    { key: "mentors", label: "Есть менторы", kind: "boolean" },
  ],
  career: [
    {
      key: "industry",
      label: "Отрасль",
      options: ["IT", "Медицина", "Промышленность", "Медиа"],
    },
    {
      key: "company",
      label: "Компания",
      options: [
        "Лаборатория «Старт»",
        "Компания «Горизонт»",
        "Студия «Искра»",
        "Завод «Спектр»",
      ],
    },
    {
      key: "activity",
      label: "Вид программы",
      options: ["Экскурсия", "Профпроба", "Стажировка"],
    },
    { key: "targeted", label: "Возможно целевое обучение", kind: "boolean" },
    {
      key: "minAge",
      label: "Минимальный возраст по безопасности, лет",
      kind: "number",
    },
    { key: "transfer", label: "Есть трансфер", kind: "boolean" },
  ],
};
export const valueLabel = (v: string | number | boolean) =>
  typeof v === "boolean" ? (v ? "Да" : "Нет") : String(v);

// ─── данные с бэкенда ───
// Справочники выше — демонстрационные (на них держатся unit-тесты). В приложении
// при запуске они заменяются настоящими: города и регионы из /api/dicts,
// варианты фильтров — из загруженных мероприятий. Массивы меняются на месте,
// чтобы все модули, которые их импортировали, увидели новые значения.

export function applyBackendDicts(d: {
  region: { code: string; name: string }[];
  city: { name: string; region_code: string }[];
}) {
  const names = Object.fromEntries(d.region.map((r) => [r.code, r.name]));
  REGIONS.splice(0, REGIONS.length, ...d.region.map((r) => r.name));
  CITIES.splice(
    0,
    CITIES.length,
    ...d.city.map((c) => ({
      id: c.name,
      name: c.name,
      region: names[c.region_code] ?? c.region_code,
    })),
  );
}

// поля с постоянным словарём — их варианты не пересчитываем
const FIXED = new Set(["grades", "format", "participation", "cost", "admission", "level"]);

export function refreshOptionsFromEvents(
  events: { [key: string]: unknown; type: string; special: object }[],
) {
  const distinct = (values: unknown[]) =>
    [...new Set(values.filter((v): v is string => typeof v === "string" && v !== ""))].sort(
      (a, b) => a.localeCompare(b, "ru"),
    );
  for (const field of GROUPS.flatMap((g) => g.fields)) {
    if (!field.options || FIXED.has(field.key)) continue;
    const values = distinct(events.map((e) => e[field.key]));
    if (values.length) field.options = values;
  }
  for (const [type, fields] of Object.entries(SPECIAL)) {
    const own = events.filter((e) => e.type === type);
    for (const field of fields) {
      if (!field.options) continue;
      const values = distinct(
        own.map((e) => (e.special as Record<string, unknown>)[field.key]),
      );
      if (values.length) field.options = values;
    }
  }
}
