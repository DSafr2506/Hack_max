import { useEffect, useRef, useState } from "react";
import type { Filters, Opportunity, Profile } from "./types";
import { GOALS, GROUPS, SPECIAL, TYPES, valueLabel } from "./data/catalog";
import { Onboarding } from "./pages/Onboarding";
import { Details } from "./pages/Details";
import { Calendar } from "./pages/Calendar";
import { ProfilePage } from "./pages/Profile";
import { Choice, dateLabel } from "./components/ui";
import { FilterSheet } from "./components/FilterSheet";
import { CategoryIcon } from "./components/CategoryIcon";
import { FeedBackground } from "./components/FeedBackground";
import {
  changeTypes,
  emptyFilters,
  filterEvents,
  profileFilters,
  toggle,
} from "./state/filters";
import { loadBrowserProfile, saveBrowserProfile } from "./state/profile";
import { firstOfMonth, initialCalendarRanges, lastOfMonth, moveDate, parseCalendarDate } from "./state/calendar";
import type { CalendarMode } from "./state/calendar";
import { clock, opportunityService } from "./services/opportunities";
import type { DemoMode } from "./services/opportunities";

const GOAL_CARDS: { label: string; goal?: string; region?: boolean }[] = [
  { label: "Льготы при поступлении", goal: GOALS[0] },
  { label: "Денежное вознаграждение", goal: GOALS[1] },
  { label: "Команда и знакомства", goal: GOALS[6] },
  { label: "Работа/профессия", goal: GOALS[3] },
  { label: "Портфолио/диплом", goal: GOALS[4] },
  { label: "Навыки", goal: GOALS[5] },
  { label: "Бесплатная поездка/смена", goal: GOALS[2] },
  { label: "Доступность из твоего региона", region: true },
];
const figmaFeedFilters = (p: Profile): Filters => ({
  ...profileFilters(p),
  goals: [GOALS[0], GOALS[3], GOALS[2]],
  soon: true,
});
const PAGE_SIZE = 3;

function paginationItems(current: number, total: number): (number | "ellipsis-start" | "ellipsis-end")[] {
  const range = (start: number, end: number) => Array.from({ length: end - start + 1 }, (_, index) => start + index);
  if (total <= 6) return range(1, total);
  if (current <= 3) return [...range(1, 5), "ellipsis-end", total];
  if (current >= total - 2) return [1, "ellipsis-start", ...range(total - 4, total)];
  return [1, "ellipsis-start", current - 1, current, current + 1, "ellipsis-end", total];
}

export default function App() {
  const [profile, setProfile] = useState(loadBrowserProfile);
  const [draft, setDraft] = useState(profile);
  const [editing, setEditing] = useState(false);
  const [view, setView] = useState<"feed" | "profile" | "calendar">("feed");
  const [calendarMode, setCalendarMode] = useState<CalendarMode>("week");
  const [calendarRanges, setCalendarRanges] = useState(initialCalendarRanges);
  const [favorites, setFavorites] = useState<string[]>([]);
  const [reminders, setReminders] = useState<string[]>([]);
  const [shareNotice, setShareNotice] = useState("");
  const [search, setSearch] = useState("");
  const [filters, setFilters] = useState<Filters>(() => figmaFeedFilters(profile));
  const [currentPage, setCurrentPage] = useState(1);
  const [sheet, setSheet] = useState(false);
  const [quickFilter, setQuickFilter] = useState<"subject" | "organizer" | null>(null);
  const quickFilterRef = useRef<HTMLDivElement>(null);
  const [event, setEvent] = useState<Opportunity | null>(null);
  const [events, setEvents] = useState<Opportunity[]>([]);
  const [mode, setMode] = useState<DemoMode>("normal");
  const [status, setStatus] = useState("loading");
  const [retry, setRetry] = useState(0);
  const [storageWarning, setStorageWarning] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    opportunityService
      .list(mode, controller.signal)
      .then((data) => {
        setEvents(data);
        setStatus("ready");
      })
      .catch((e) => {
        if (e.name !== "AbortError") setStatus("error");
      });
    return () => controller.abort();
  }, [mode, retry]);
  useEffect(() => {
    if (!quickFilter) return;
    const closeOnOutsidePointer = (e: PointerEvent) => {
      if (e.target instanceof Node && !quickFilterRef.current?.contains(e.target))
        setQuickFilter(null);
    };
    const closeOnEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape") setQuickFilter(null);
    };
    window.addEventListener("pointerdown", closeOnOutsidePointer);
    window.addEventListener("keydown", closeOnEscape);
    return () => {
      window.removeEventListener("pointerdown", closeOnOutsidePointer);
      window.removeEventListener("keydown", closeOnEscape);
    };
  }, [quickFilter]);
  useEffect(() => setCurrentPage(1), [filters, search, mode]);
  function load(m: DemoMode) {
    setStatus("loading");
    setMode(m);
    setRetry((n) => n + 1);
  }
  function updateDraft(p: Profile) {
    setDraft(p);
    if (!editing) setStorageWarning(!saveBrowserProfile(p));
  }
  function complete() {
    const p = { ...draft, completed: true };
    setProfile(p);
    setDraft(p);
    setStorageWarning(!saveBrowserProfile(p));
    setFilters(figmaFeedFilters(p));
    setEditing(false);
    setView("feed");
    window.scrollTo(0, 0);
  }
  const found = filterEvents(events, filters, profile, clock.today());
  const participating = events.filter((item) => item.isParticipating).map((item) => item.id);
  const visibleFound = found.filter((item) =>
    (item.title + " " + item.organizer + " " + item.description)
      .toLocaleLowerCase("ru")
      .includes(search.trim().toLocaleLowerCase("ru")),
  );
  const pageCount = Math.ceil(visibleFound.length / PAGE_SIZE);
  const safePage = Math.min(currentPage, Math.max(pageCount, 1));
  const pageEvents = visibleFound.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE);
  function toggleId(list: string[], setList: (next: string[]) => void, id: string) {
    setList(list.includes(id) ? list.filter((item) => item !== id) : [...list, id]);
  }
  async function shareOpportunity(item: Pick<Opportunity, "title">) {
    try {
      if (navigator.share) {
        await navigator.share({ title: item.title, text: item.title, url: window.location.href });
      } else if (navigator.clipboard) {
        await navigator.clipboard.writeText(window.location.href);
        setShareNotice("Ссылка скопирована");
      } else {
        setShareNotice("Поделиться можно через меню браузера");
      }
    } catch {
      setShareNotice("Не удалось поделиться ссылкой");
    }
  }
  const subjectFilterCount = filters.special.subject?.length ?? 0;
  const organizerOptions = GROUPS.flatMap((group) => group.fields).find((field) => field.key === "organizerType")?.options ?? [];
  const subjectOptions = SPECIAL.olympiad.find((field) => field.key === "subject")?.options ?? [];
  const organizerFilterCount = filters.values.organizerType?.length ?? 0;
  function openEventCalendar(item: Opportunity) {
    const weekStart = moveDate(item.start, -((parseCalendarDate(item.start).getUTCDay() + 6) % 7));
    setCalendarRanges({
      week: { start: weekStart, end: moveDate(weekStart, 6) },
      months: { start: firstOfMonth(item.start), end: lastOfMonth(item.end) },
    });
    setCalendarMode("week");
    setView("calendar");
    setEvent(null);
    window.scrollTo(0, 0);
  }
  if (!profile.completed || editing)
    return (
      <>
        {storageWarning && (
          <p role="status" className="notice">
            Не удалось сохранить профиль на устройстве. Он доступен до закрытия
            страницы.
          </p>
        )}
        <Onboarding
          profile={draft}
          onChange={updateDraft}
          onComplete={complete}
          editing={editing}
          onCancel={
            editing
              ? () => {
                  setDraft(profile);
                  setEditing(false);
                }
              : undefined
          }
        />
      </>
    );
  if (event) return (
    <div className="app-shell details-shell">
      <FeedBackground />
      <header className="app-header">
        <button className="header-control" aria-label="Назад" onClick={() => setEvent(null)}>×</button>
        <button className="brand" onClick={() => { setEvent(null); setView("feed"); }}>Дерзай</button>
        <button className="header-control" aria-label="Обновить мини-приложение" title="Обновить" onClick={() => window.location.reload()}>⋮</button>
      </header>
      <Details
        event={event}
        isParticipating={event.isParticipating === true}
        onGoToCalendar={() => openEventCalendar(event)}
      />
      <nav className="bottom-nav" aria-label="Главная навигация">
        <button aria-label="✦ Агрегатор" aria-current="page" onClick={() => { setEvent(null); setView("feed"); }}>
          <span className="nav-icon" aria-hidden="true"><NavGlyph kind="feed" /></span><small>Агрегатор</small>
        </button>
        <button aria-label="◎ Профиль" onClick={() => { setEvent(null); setView("profile"); }}>
          <span className="nav-icon" aria-hidden="true"><NavGlyph kind="profile" /></span><small>Профиль</small>
        </button>
        <button aria-label="▣ Календарь" onClick={() => { setEvent(null); setView("calendar"); }}>
          <span className="nav-icon" aria-hidden="true"><NavGlyph kind="calendar" /></span><small>Календарь</small>
        </button>
      </nav>
    </div>
  );
  return (
    <div className="app-shell">
      {view === "feed" && <FeedBackground />}
      <header className="app-header">
        <button className="header-control" aria-label="На главную" onClick={() => setView("feed")}>×</button>
        <button className="brand" onClick={() => setView("feed")}>Дерзай</button>
        <button className="header-control" aria-label="Обновить мини-приложение" title="Обновить" onClick={() => window.location.reload()}>⋮</button>
      </header>
      <div className="page">
        {storageWarning && (
          <p className="notice" role="status">
            Хранилище недоступно. Профиль сохранён только на время сеанса.
          </p>
        )}
        {view === "profile" ? (
          <ProfilePage
            profile={profile}
            events={events}
            favorites={favorites}
            reminders={reminders}
            participating={participating}
            onToggleFavorite={(id) => toggleId(favorites, setFavorites, id)}
            onToggleReminder={(id) => toggleId(reminders, setReminders, id)}
            onEdit={() => {
              setDraft(profile);
              setEditing(true);
            }}
            onOpen={(item) => {
              setEvent(item);
              window.scrollTo(0, 0);
            }}
          />
        ) : view === "calendar" ? (
          <Calendar
            events={events}
            mode={calendarMode}
            onChangeMode={setCalendarMode}
            ranges={calendarRanges}
            onChangeRanges={setCalendarRanges}
            onBack={() => setView("feed")}
            onOpen={(title) => {
              const item = events[0];
              if (item) setEvent({ ...item, title });
              window.scrollTo(0, 0);
            }}
          />
        ) : (
          <>
            <div className="feed-toolbar">
              <button
                className="feed-filter-trigger"
                aria-label="Открыть фильтры"
                title="Фильтры"
                onClick={() => setSheet(true)}
              >
                <svg viewBox="0 0 32 32" aria-hidden="true"><path d="M4 9h24M4 23h24"/><circle cx="10" cy="9" r="3.2"/><circle cx="22" cy="23" r="3.2"/></svg>
              </button>
              <label className="feed-search">
                <svg className="search-icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="10.8" cy="10.8" r="7.3"/><path d="m16.2 16.2 5 5"/></svg>
                <input
                  type="search"
                  value={search}
                  placeholder="Поиск"
                  aria-label="Поиск возможностей"
                  onChange={(e) => setSearch(e.target.value)}
                />
                {search && <button aria-label="Очистить поиск" onClick={() => setSearch("")}>×</button>}
              </label>
            </div>
            <nav className="category-row" aria-label="Категории возможностей">
              {([
                ["olympiad", "Олимпиады"],
                ["school", "Образовательные смены"],
                ["career", "Профориентация и карьера"],
                ["hackathon", "Хакатоны"],
              ] as const).map(([type, title]) => (
                <button
                  key={type}
                  className={filters.types.includes(type) ? "category active" : "category"}
                  aria-pressed={filters.types.includes(type)}
                  onClick={() => setFilters(changeTypes(filters, filters.types.includes(type) ? filters.types.filter((item) => item !== type) : [...filters.types, type]))}
                >
                  <CategoryIcon kind={type} />
                  <span>{title}</span>
                </button>
              ))}
            </nav>
            <section aria-labelledby="goals-title">
              <div className="section-heading">
                <h2 id="goals-title">Что для тебя важно?</h2>
              </div>
              <div className="goals">
                {GOAL_CARDS.map(({ label, goal, region }) => (
                  <Choice
                    className="goal-chip"
                    key={label}
                    selected={region ? filters.regionOnly : filters.goals.includes(goal!)}
                    onClick={() =>
                      setFilters(
                        region
                          ? { ...filters, regionOnly: !filters.regionOnly }
                          : { ...filters, goals: toggle(filters.goals, goal!) },
                      )
                    }
                  >
                    {label}
                  </Choice>
                ))}
              </div>
            </section>
            <section className="feed-list-section" aria-label="Возможности для тебя">
              <div className="quick-filter-zone" ref={quickFilterRef}>
                <div className="quick-filter-row" aria-label="Быстрые фильтры">
                <button
                  className={filters.soon ? "quick-filter selected" : "quick-filter"}
                  aria-pressed={filters.soon}
                  onClick={() => setFilters({ ...filters, soon: !filters.soon })}
                >
                  Скоро дедлайн
                </button>
                <span className={`quick-filter subject-filter${subjectFilterCount ? " has-selection" : ""}`}>
                  <button
                    className="quick-filter-label"
                    aria-haspopup="dialog"
                    aria-expanded={quickFilter === "subject"}
                    onClick={() => setQuickFilter(quickFilter === "subject" ? null : "subject")}
                  >
                    <span>{subjectFilterCount ? `Предмет +${subjectFilterCount}` : "Предмет"}</span>
                    <svg viewBox="0 0 16 16" aria-hidden="true"><path d="m3 6 5 5 5-5" /></svg>
                  </button>
                  {subjectFilterCount > 0 && (
                    <button
                      className="quick-filter-clear"
                      aria-label="Сбросить фильтр по предмету"
                      onClick={() => setFilters({ ...filters, special: { ...filters.special, subject: [] } })}
                    >×</button>
                  )}
                </span>
                <button
                  className={`quick-filter organizer-filter${organizerFilterCount ? " selected" : ""}`}
                  aria-haspopup="dialog"
                  aria-expanded={quickFilter === "organizer"}
                  onClick={() => setQuickFilter(quickFilter === "organizer" ? null : "organizer")}
                >
                  {organizerFilterCount ? `Организатор +${organizerFilterCount}` : "Тип организатора"}
                  <svg viewBox="0 0 16 16" aria-hidden="true"><path d="m3 6 5 5 5-5" /></svg>
                </button>
                </div>
                {quickFilter && (
                  <section className="quick-filter-popover" role="dialog" aria-label={quickFilter === "subject" ? "Фильтр по предмету" : "Фильтр по типу организатора"}>
                    <h3>{quickFilter === "subject" ? "Предмет" : "Тип организатора"}</h3>
                    <div className="chips quick-filter-options">
                      {(quickFilter === "subject" ? subjectOptions : organizerOptions).map((option) => {
                        const values = quickFilter === "subject" ? filters.special.subject ?? [] : filters.values.organizerType ?? [];
                        return (
                          <Choice
                            key={String(option)}
                            selected={values.includes(option)}
                            onClick={() => setFilters(quickFilter === "subject"
                              ? { ...filters, special: { ...filters.special, subject: toggle(values, option) } }
                              : { ...filters, values: { ...filters.values, organizerType: toggle(values, option) } })}
                          >
                            {valueLabel(option)}
                          </Choice>
                        );
                      })}
                    </div>
                    <footer>
                      <button
                        className="quick-filter-reset"
                        disabled={quickFilter === "subject" ? !subjectFilterCount : !organizerFilterCount}
                        onClick={() => setFilters(quickFilter === "subject"
                          ? { ...filters, special: { ...filters.special, subject: [] } }
                          : { ...filters, values: { ...filters.values, organizerType: [] } })}
                      >Сбросить</button>
                      <button className="quick-filter-done" onClick={() => setQuickFilter(null)}>Готово</button>
                    </footer>
                  </section>
                )}
              </div>
              <p className="result-count visually-hidden" role="status">
                {status === "ready"
                  ? `${visibleFound.length} возможностей`
                  : status === "error" ? "Ошибка загрузки" : "Загружаем возможности…"}
              </p>
              {status === "loading" ? (
                <div className="glass loading" role="status">
                  Собираем вашу подборку…
                </div>
              ) : status === "error" ? (
                <div className="glass" role="alert">
                  <h3>Не получилось загрузить события</h3>
                  <p>Это демонстрация ошибки сервиса.</p>
                  <button className="primary" onClick={() => load("normal")}>
                    Повторить попытку
                  </button>
                </div>
              ) : !visibleFound.length ? (
                <div className="glass">
                  <h3>Пока ничего не нашлось</h3>
                  <p>Попробуйте снять часть ограничений.</p>
                  <button
                    onClick={() => {
                      setFilters(emptyFilters());
                      if (mode === "empty") load("normal");
                    }}
                  >
                    Показать все возможности
                  </button>
                </div>
              ) : (
                <div className="event-list">
                  {pageEvents.map((e) => (
                    <article className="event-item" key={e.id}>
                      <button
                        className={"event-card " + e.type}
                        onClick={() => {
                          setEvent(e);
                          window.scrollTo(0, 0);
                        }}
                      >
                        <div className="card-top"><span>{TYPES[e.type]}</span></div>
                        <h3>{e.title}</h3>
                        <p className="organizer">{e.organizer}</p>
                        <p>{e.description}</p>
                        <div className="tags">
                          <span>{e.format} · {e.region}</span>
                          <span>{e.grades.join(", ")} классы</span>
                        </div>
                        <p className="results">{e.results.join(" · ")}</p>
                        <div className="card-bottom">
                          <span>До {dateLabel(e.deadline)}</span>
                          <strong>{e.cost}{e.price ? " · " + e.price + " ₽" : ""}</strong>
                        </div>
                      </button>
                      <div className="event-actions">
                        <button aria-label="Поделиться возможностью" title="Поделиться" onClick={() => { void shareOpportunity(e); }}>
                          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14.5 5.5 20 11l-5.5 5.5M20 11H9a5 5 0 0 0-5 5v2"/></svg>
                        </button>
                        <button aria-label={reminders.includes(e.id) ? "Убрать напоминание" : "Добавить напоминание"} aria-pressed={reminders.includes(e.id)} onClick={() => toggleId(reminders, setReminders, e.id)}>
                          <svg viewBox="0 0 24 24" aria-hidden="true" className={reminders.includes(e.id) ? "is-filled" : ""}><path d="M18 9a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9ZM10 21h4"/></svg>
                        </button>
                        <button aria-label={favorites.includes(e.id) ? "Убрать из избранного" : "Добавить в избранное"} aria-pressed={favorites.includes(e.id)} onClick={() => toggleId(favorites, setFavorites, e.id)}>
                          <svg viewBox="0 0 24 24" aria-hidden="true" className={favorites.includes(e.id) ? "is-filled" : ""}><path d="M20.8 8.7c0 4.2-8.8 10.1-8.8 10.1S3.2 12.9 3.2 8.7A4.4 4.4 0 0 1 12 7.2a4.4 4.4 0 0 1 8.8 1.5Z"/></svg>
                        </button>
                      </div>
                    </article>
                  ))}
                </div>
              )}
              {pageCount > 1 && (
                <nav className="opportunity-pagination" aria-label="Страницы возможностей">
                  {paginationItems(safePage, pageCount).map((item, index) =>
                    typeof item === "number" ? (
                      <button
                        key={item}
                        aria-current={safePage === item ? "page" : undefined}
                        aria-label={`Страница ${item}`}
                        onClick={() => {
                          setCurrentPage(item);
                          window.scrollTo({ top: 0, behavior: "smooth" });
                        }}
                      >{item}</button>
                    ) : (
                      <span className="pagination-ellipsis" key={item + index} aria-hidden="true">…</span>
                    ),
                  )}
                </nav>
              )}
              {shareNotice && <p className="share-notice" role="status">{shareNotice}</p>}
            </section>
            <details className="demo-controls">
              <summary>Демонстрационный режим</summary>
              <p>
                Все 16 мероприятий вымышлены. Дата демо:{" "}
                {dateLabel(clock.today())}. Условия не являются реальными
                предложениями.
              </p>
              <label>
                Состояние сервиса
                <select
                  value={mode}
                  onChange={(e) => load(e.target.value as DemoMode)}
                >
                  <option value="normal">Обычная загрузка</option>
                  <option value="loading">Медленная загрузка (5 секунд)</option>
                  <option value="error">Ошибка</option>
                  <option value="empty">Пустая выдача</option>
                </select>
              </label>
            </details>
          </>
        )}
      </div>
      <nav className="bottom-nav" aria-label="Главная навигация">
        <button
          aria-label="✦ Агрегатор"
          aria-current={view === "feed" ? "page" : undefined}
          onClick={() => setView("feed")}
        >
          <span className="nav-icon" aria-hidden="true"><NavGlyph kind="feed" /></span><small>Агрегатор</small>
        </button>
        <button
          aria-label="◎ Профиль"
          aria-current={view === "profile" ? "page" : undefined}
          onClick={() => setView("profile")}
        >
          <span className="nav-icon" aria-hidden="true"><NavGlyph kind="profile" /></span><small>Профиль</small>
        </button>
        <button
          aria-label="▣ Календарь"
          aria-current={view === "calendar" ? "page" : undefined}
          onClick={() => setView("calendar")}
        >
          <span className="nav-icon" aria-hidden="true"><NavGlyph kind="calendar" /></span><small>Календарь</small>
        </button>
      </nav>
      {sheet && (
        <FilterSheet
          filters={filters}
          profile={profile}
          onClose={() => setSheet(false)}
          onApply={(f) => {
            setFilters(f);
            setSheet(false);
          }}
        />
      )}
    </div>
  );
}

function NavGlyph({ kind }: { kind: "feed" | "profile" | "calendar" }) {
  if (kind === "feed") return <svg viewBox="0 0 28 28"><path d="M14 2v8M14 18v8M2 14h8M18 14h8M5.5 5.5l5.7 5.7M16.8 16.8l5.7 5.7M22.5 5.5l-5.7 5.7M11.2 16.8l-5.7 5.7" /></svg>;
  if (kind === "profile") return <svg viewBox="0 0 28 28"><circle cx="14" cy="8" r="4" /><rect x="5" y="15" width="18" height="10" rx="4" /></svg>;
  return <svg viewBox="0 0 28 28"><rect x="4" y="5" width="20" height="19" rx="4" /><path d="M9 3v5M19 3v5M4 11h20" /></svg>;
}
