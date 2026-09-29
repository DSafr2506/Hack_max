import { useState } from "react";
import type { Opportunity, Profile as StudentProfile } from "../types";
import { CITIES, TYPES } from "../data/catalog";
import { BackArrow, dateLabel } from "../components/ui";

type Section = "main" | "favorites" | "reminders" | "participation";

const profileSampleEvent: Opportunity = {
  id: "figma-sirius-math",
  type: "school",
  title: "«Сириус»: январская математическая программа",
  organizer: "Образовательный центр «Сириус»",
  description:
    "Смена 5–26 января 2027 в Образовательном центре «Сириус». Отбор: дистанционный учебно-отборочный курс с тестированием и очный отборочный тур 31 октября. Оплата проезда по России, питания и пребывания — за счёт Образовательного фонда «Талант и успех».",
  format: "Офлайн",
  region: "Сочи",
  eligibleRegions: ["*"],
  grades: [8, 9],
  goals: [],
  results: ["Бесплатная поездка / смена", "Навыки", "Команда и знакомства"],
  opens: "2026-09-01",
  deadline: "2026-09-27",
  start: "2027-01-05",
  end: "2027-01-26",
  duration: 22,
  cost: "Бесплатно",
  price: 0,
  participation: "Один",
  admission: "Открытый отбор",
  level: "Всероссийский",
  organizerType: "Образовательный центр",
  direction: "Математика",
  special: {
    schoolDirection: "Математика",
    selection: "Открытый отбор",
    quotaRegion: "Все регионы",
    season: "Зима 2027",
  },
};

function ActionIcon({ name, active = false }: { name: "share" | "bell" | "heart"; active?: boolean }) {
  if (name === "share") {
    return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14.5 5.5 20 11l-5.5 5.5M20 11H9a5 5 0 0 0-5 5v2" /></svg>;
  }
  if (name === "bell") {
    return <svg viewBox="0 0 24 24" aria-hidden="true" className={active ? "is-filled" : ""}><path d="M18 9a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9ZM10 21h4" /></svg>;
  }
  return <svg viewBox="0 0 24 24" aria-hidden="true" className={active ? "is-filled" : ""}><path d="M20.8 8.7c0 4.2-8.8 10.1-8.8 10.1S3.2 12.9 3.2 8.7A4.4 4.4 0 0 1 12 7.2a4.4 4.4 0 0 1 8.8 1.5Z" /></svg>;
}

function FeatureArt({ name }: { name: "heart" | "bell" | "badge" }) {
  return <img className={"profile-feature-art profile-feature-art--" + name} src={"/assets/figma/profile-" + name + ".png"} width="151" height="151" alt="" aria-hidden="true" />;
}

function FeatureCard({ title, description, icon, onClick }: { title: string; description: string; icon: "heart" | "bell" | "badge"; onClick: () => void }) {
  return <button className="profile-feature-card" onClick={onClick}>
    <span className="profile-feature-copy"><strong>{title}</strong><small>{description}</small></span>
    <FeatureArt name={icon} />
  </button>;
}

export function ProfilePage({
  profile,
  events,
  favorites,
  reminders,
  participating,
  onToggleFavorite,
  onToggleReminder,
  onEdit,
  onOpen,
}: {
  profile: StudentProfile;
  events: Opportunity[];
  favorites: string[];
  reminders: string[];
  participating: string[];
  onToggleFavorite: (id: string) => void;
  onToggleReminder: (id: string) => void;
  onEdit: () => void;
  onOpen: (event: Opportunity) => void;
}) {
  const [section, setSection] = useState<Section>("main");
  const [mockFavorites, setMockFavorites] = useState<boolean[]>([]);
  const [mockReminders, setMockReminders] = useState<boolean[]>([]);
  const [notice, setNotice] = useState("");
  const city = CITIES.find((item) => item.id === profile.cityId);
  const heading = section === "favorites" ? "Избранное" : section === "reminders" ? "Напоминания" : "Участия";
  const selectedEvents = section === "favorites"
    ? events.filter((event) => favorites.includes(event.id))
    : section === "reminders"
      ? events.filter((event) => reminders.includes(event.id))
      : events.filter((event) => participating.includes(event.id));
  const useReferenceCards = selectedEvents.length === 0;
  const cards = useReferenceCards
    ? [0, 1, 2].map((index) => ({ event: profileSampleEvent, key: "figma-sample-" + index, demoIndex: index as number | null }))
    : selectedEvents.map((event) => ({ event, key: event.id, demoIndex: null as number | null }));
  const goalItems = profile.goalText
    .split(/\r?\n|;\s*/)
    .map((goal) => goal.trim())
    .filter(Boolean);
  const moveTo = (next: Section) => {
    setSection(next);
    window.scrollTo(0, 0);
  };
  const shareEvent = async (event: Opportunity) => {
    const data = { title: event.title, text: event.title, url: window.location.href };
    try {
      if (navigator.share) await navigator.share(data);
      else if (navigator.clipboard) {
        await navigator.clipboard.writeText(window.location.href);
        setNotice("Ссылка скопирована");
      } else setNotice("Поделиться можно через меню браузера");
    } catch {
      setNotice("Не удалось скопировать ссылку");
    }
  };

  if (section !== "main") {
    return (
      <main className="profile-page profile-subpage">
        <button className="profile-back" aria-label="Назад в профиль" onClick={() => moveTo("main")}><BackArrow className="figma-back-arrow" /></button>
        <h1>{heading}</h1>
        <div className="profile-event-list">
          {cards.map(({ event, key, demoIndex }) => {
            const isMock = demoIndex !== null;
            const favorite = isMock ? (mockFavorites[demoIndex!] ?? section === "favorites") : favorites.includes(event.id);
            const reminder = isMock ? (mockReminders[demoIndex!] ?? section === "reminders") : reminders.includes(event.id);
            const toggleMock = (kind: "favorite" | "reminder") => {
              if (demoIndex === null) {
                if (kind === "favorite") onToggleFavorite(event.id);
                else onToggleReminder(event.id);
                return;
              }
              if (kind === "favorite") setMockFavorites((current) => Array.from({ length: 3 }, (_, index) => index === demoIndex ? !favorite : current[index] ?? section === "favorites"));
              else setMockReminders((current) => Array.from({ length: 3 }, (_, index) => index === demoIndex ? !reminder : current[index] ?? section === "reminders"));
            };
            return (
              <article className="profile-opportunity" key={key}>
                <div className="profile-opportunity-top">
                  <span className="profile-type-chip">{TYPES[event.type]}</span>
                  {section === "participation" && <span className="profile-participating">Участвую</span>}
                  <div className="profile-opportunity-actions">
                    <button aria-label="Поделиться возможностью" title="Поделиться" onClick={() => { void shareEvent(event); }}><ActionIcon name="share" /></button>
                    <button aria-label={reminder ? "Убрать напоминание" : "Добавить напоминание"} aria-pressed={reminder} onClick={() => toggleMock("reminder")}><ActionIcon name="bell" active={reminder} /></button>
                    <button aria-label={favorite ? "Убрать из избранного" : "Добавить в избранное"} aria-pressed={favorite} onClick={() => toggleMock("favorite")}><ActionIcon name="heart" active={favorite} /></button>
                  </div>
                </div>
                <button
                  className="profile-opportunity-open"
                  onClick={() => onOpen(section === "participation" ? { ...event, isParticipating: true } : event)}
                >
                  <strong>{event.title}</strong>
                  <span className="profile-opportunity-organizer">{event.organizer}</span>
                  <span className="profile-opportunity-description">{event.description}</span>
                </button>
                <div className="profile-opportunity-tags">
                  <span>{event.format} · {event.region}</span>
                  <span>{event.grades.join(", ")} классы</span>
                </div>
                <p className="profile-opportunity-results">{event.results.join(" · ")}</p>
                <div className="profile-opportunity-footer">
                  <span>До {dateLabel(event.deadline)}</span>
                  <strong>{event.cost}</strong>
                </div>
              </article>
            );
          })}
        </div>
        <p className="profile-live-notice" role="status">{notice}</p>
      </main>
    );
  }

  return (
    <main className="profile-page">
      <p className="profile-eyebrow">Ваша отправная точка</p>
      <h1>Мой профиль</h1>
      <section className="profile-summary">
        <h2>{profile.grade} класс · {city?.name || "Город не выбран"}</h2>
        <p className="profile-region">{city?.region || "Ваш регион"}</p>
        <p className="profile-types">{profile.types.map((type) => TYPES[type]).join(", ")}</p>
        <strong className="profile-goal-label">Цели на год</strong>
        <div className="profile-goals">
          {(goalItems.length ? goalItems : ["Выиграть олимпиаду", "Пройти в финал на хакатоне"]).map((goal) => <span key={goal}>{goal}</span>)}
        </div>
        <button className="profile-edit-button" onClick={onEdit}>Редактировать профиль</button>
        <button className="profile-restart" onClick={onEdit}><span>Пройти онбординг заново</span></button>
      </section>
      <section className="profile-feature-list" aria-label="Разделы профиля">
        <FeatureCard title="Избранное" description="Ваш личный список интересных возможностей и мероприятий" icon="heart" onClick={() => moveTo("favorites")} />
        <FeatureCard title="Напоминания" description="Мероприятия, о старте регистрации которых мы напомним в чат-боте" icon="bell" onClick={() => moveTo("reminders")} />
        <FeatureCard title="Участия" description="Ваш трекер активности" icon="badge" onClick={() => moveTo("participation")} />
      </section>
    </main>
  );
}
