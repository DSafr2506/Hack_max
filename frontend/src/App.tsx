import { useEffect, useState } from "react";
import type { EventType, Filters, Opportunity, Profile } from "./types";
import {
  CITIES,
  GOALS,
  GROUPS,
  SPECIAL,
  TYPES,
  valueLabel,
} from "./data/catalog";
import { Onboarding } from "./pages/Onboarding";
import { Details } from "./pages/Details";
import { Choice, dateLabel } from "./components/ui";
import { FilterSheet } from "./components/FilterSheet";
import {
  changeTypes,
  emptyFilters,
  filterEvents,
  profileFilters,
  toggle,
} from "./state/filters";
import { loadBrowserProfile, saveBrowserProfile } from "./state/profile";
import { clock, opportunityService } from "./services/opportunities";
import type { DemoMode } from "./services/opportunities";
import { environment } from "./integration/max";
export default function App() {
  const [profile, setProfile] = useState(loadBrowserProfile);
  const [draft, setDraft] = useState(profile);
  const [editing, setEditing] = useState(false);
  const [view, setView] = useState<"feed" | "profile">("feed");
  const [filters, setFilters] = useState<Filters>(() =>
    profileFilters(profile),
  );
  const [sheet, setSheet] = useState(false);
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
    setFilters(profileFilters(p));
    setEditing(false);
    setView("feed");
    window.scrollTo(0, 0);
  }
  const found = filterEvents(events, filters, profile, clock.today());
  const city = CITIES.find((c) => c.id === profile.cityId);
  const labels = [
    ...filters.types.map((t) => TYPES[t]),
    ...filters.goals,
    ...Object.entries(filters.values).flatMap(([k, v]) =>
      v.map(
        (x) =>
          `${GROUPS.flatMap((g) => g.fields).find((f) => f.key === k)?.label}: ${valueLabel(x)}`,
      ),
    ),
    ...(filters.regionOnly
      ? [`Участники из: ${city?.region ?? "город не выбран"}`]
      : []),
    ...(filters.soon ? ["Дедлайн: ближайшие 7 дней"] : []),
    ...Object.entries(filters.ranges)
      .filter(([, r]) => r.min || r.max)
      .map(
        ([k, r]) =>
          `${GROUPS.flatMap((g) => g.fields).find((f) => f.key === k)?.label}: ${r.min || "…"} — ${r.max || "…"}`,
      ),
    ...Object.entries(filters.special).flatMap(([k, v]) =>
      v.map(
        (x) =>
          `${filters.types.length === 1 ? SPECIAL[filters.types[0]].find((f) => f.key === k)?.label : k}: ${valueLabel(x)}`,
      ),
    ),
    ...Object.entries(filters.specialRanges)
      .filter(([, r]) => r.min || r.max)
      .map(
        ([k, r]) =>
          `${filters.types.length === 1 ? SPECIAL[filters.types[0]].find((f) => f.key === k)?.label : k}: ${r.min || "…"} — ${r.max || "…"}`,
      ),
  ];
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
  if (event) return <Details event={event} onBack={() => setEvent(null)} />;
  return (
    <div className="app-shell">
      <header className="app-header">
        <a
          href="#"
          onClick={(e) => {
            e.preventDefault();
            setView("feed");
          }}
          className="brand"
        >
          <span>✦</span> дерзай
        </a>
        <span className="demo-badge">ДЕМО</span>
      </header>
      <main className="page">
        {storageWarning && (
          <p className="notice" role="status">
            Хранилище недоступно. Профиль сохранён только на время сеанса.
          </p>
        )}
        {view === "profile" ? (
          <>
            <p className="eyebrow">ВАША ОТПРАВНАЯ ТОЧКА</p>
            <h1>Мой профиль</h1>
            <section className="glass">
              <h2>
                {profile.grade} класс · {city?.name}
              </h2>
              <p>{city?.region}</p>
              <p>{profile.types.map((t) => TYPES[t]).join(", ")}</p>
              <h3>Цели на год</h3>
              <p className="preserve">
                {profile.goalText || "Вы пока не добавили цели"}
              </p>
              <button
                className="primary"
                onClick={() => {
                  setDraft(profile);
                  setEditing(true);
                }}
              >
                Редактировать профиль
              </button>
              <button
                className="text-button"
                onClick={() => {
                  const p = { ...profile, completed: false };
                  setProfile(p);
                  setDraft(p);
                  setStorageWarning(!saveBrowserProfile(p));
                }}
              >
                Пройти онбординг заново
              </button>
            </section>
            <p className="hint">
              {environment.name}. Данные остаются на этом устройстве.
            </p>
          </>
        ) : (
          <>
            <p className="eyebrow">БОЛЬШОЕ НАЧИНАЕТСЯ С ИНТЕРЕСА</p>
            <h1>
              Твоя следующая
              <br />
              <em>возможность</em>
            </h1>
            <p className="intro">
              Пробуй новое. Находи своих.
              <br />
              Выбирай то, что приблизит к цели.
            </p>
            <section aria-labelledby="goals-title">
              <div className="section-heading">
                <h2 id="goals-title">Что для тебя важно?</h2>
                <span>01 / ЦЕЛИ</span>
              </div>
              <div className="goals">
                {GOALS.map((g, i) => (
                  <Choice
                    className="goal-chip"
                    key={g}
                    selected={filters.goals.includes(g)}
                    onClick={() =>
                      setFilters({
                        ...filters,
                        goals: toggle(filters.goals, g),
                      })
                    }
                  >
                    <span aria-hidden="true">
                      {["↗", "₽", "☀", "⌘", "☆", "✦", "◎"][i]}
                    </span>
                    {g}
                  </Choice>
                ))}
              </div>
            </section>
            <section>
              <div className="section-heading">
                <h2>Подборка для тебя</h2>
                <span>02 / КАТАЛОГ</span>
              </div>
              <div className="chips quick">
                <Choice
                  selected={filters.values.cost?.includes("Бесплатно") ?? false}
                  onClick={() =>
                    setFilters({
                      ...filters,
                      values: {
                        ...filters.values,
                        cost: filters.values.cost?.includes("Бесплатно")
                          ? []
                          : ["Бесплатно"],
                      },
                    })
                  }
                >
                  Бесплатно
                </Choice>
                <Choice
                  selected={filters.regionOnly}
                  onClick={() =>
                    setFilters({ ...filters, regionOnly: !filters.regionOnly })
                  }
                >
                  Доступно из моего региона
                </Choice>
                <Choice
                  selected={filters.soon}
                  onClick={() =>
                    setFilters({ ...filters, soon: !filters.soon })
                  }
                >
                  Дедлайн скоро
                </Choice>
                <Choice
                  selected={filters.values.format?.includes("Онлайн") ?? false}
                  onClick={() =>
                    setFilters({
                      ...filters,
                      values: {
                        ...filters.values,
                        format: filters.values.format?.includes("Онлайн")
                          ? []
                          : ["Онлайн"],
                      },
                    })
                  }
                >
                  Онлайн
                </Choice>
              </div>
              <div className="filter-toolbar">
                <label>
                  Тип мероприятия
                  <select
                    value={filters.types.length === 1 ? filters.types[0] : ""}
                    onChange={(e) =>
                      setFilters(
                        changeTypes(
                          filters,
                          e.target.value ? [e.target.value as EventType] : [],
                        ),
                      )
                    }
                  >
                    <option value="">
                      {filters.types.length > 1
                        ? "Несколько типов"
                        : "Все типы"}
                    </option>
                    {Object.entries(TYPES).map(([id, title]) => (
                      <option key={id} value={id}>
                        {title}
                      </option>
                    ))}
                  </select>
                </label>
                <button
                  className="filter-button"
                  onClick={() => setSheet(true)}
                >
                  ☷ Все фильтры
                </button>
              </div>
              <details className="applied">
                <summary>Применённые ограничения · {labels.length}</summary>
                {labels.length ? (
                  <ul>
                    {labels.map((s, i) => (
                      <li key={i}>{s}</li>
                    ))}
                  </ul>
                ) : (
                  <p>Весь каталог без ограничений</p>
                )}
              </details>
              <div className="reset-row">
                <button
                  className="text-button"
                  onClick={() => setFilters(emptyFilters())}
                >
                  Сбросить фильтры
                </button>
                <button
                  className="text-button"
                  onClick={() => setFilters(profileFilters(profile))}
                >
                  По моему профилю
                </button>
              </div>
              <p className="result-count" role="status">
                {status === "ready"
                  ? `${found.length} возможностей`
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
              ) : !found.length ? (
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
                  {found.map((e) => (
                    <button
                      className={`event-card ${e.type}`}
                      key={e.id}
                      onClick={() => {
                        setEvent(e);
                        window.scrollTo(0, 0);
                      }}
                    >
                      <div className="card-top">
                        <span>{TYPES[e.type]}</span>
                        <span aria-hidden="true">↗</span>
                      </div>
                      <h3>{e.title}</h3>
                      <p className="organizer">{e.organizer}</p>
                      <p>{e.description}</p>
                      <div className="tags">
                        <span>
                          {e.format} · {e.region}
                        </span>
                        <span>{e.grades.join(", ")} классы</span>
                      </div>
                      <p className="results">{e.results.join(" · ")}</p>
                      <div className="card-bottom">
                        <span>До {dateLabel(e.deadline)}</span>
                        <strong>
                          {e.cost}
                          {e.price ? ` · ${e.price} ₽` : ""}
                        </strong>
                      </div>
                    </button>
                  ))}
                </div>
              )}
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
      </main>
      <nav className="bottom-nav" aria-label="Главная навигация">
        <button
          aria-current={view === "feed" ? "page" : undefined}
          onClick={() => setView("feed")}
        >
          ✦ Возможности
        </button>
        <button
          aria-current={view === "profile" ? "page" : undefined}
          onClick={() => setView("profile")}
        >
          ◎ Профиль
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
