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
