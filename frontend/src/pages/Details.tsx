import { useState } from "react";
import type { Opportunity } from "../types";
import { SPECIAL, valueLabel } from "../data/catalog";
import { dateLabel } from "../components/ui";
export function Details({
  event: e,
  isParticipating,
  onGoToCalendar,
}: {
  event: Opportunity;
  isParticipating: boolean;
  onGoToCalendar: () => void;
}) {
  const [registrationNotice, setRegistrationNotice] = useState(false);
  const bool = (v: boolean | undefined) =>
    v === undefined ? "Не указано" : v ? "Да" : "Нет";
  const registrationUrl = e.source && /^https:\/\//.test(e.source) ? e.source : null;
  function continueToOpportunity() {
    if (registrationUrl) window.open(registrationUrl, "_blank", "noopener,noreferrer");
    else setRegistrationNotice(true);
  }
  return (
    <main className="page event-details">
      <h1>{e.title}</h1>
      <p className="details-organizer">{e.organizer}</p>
      <section className="glass details-card">
        <h2>О ВОЗМОЖНОСТИ</h2>
        <p>{e.description}</p>
        <h3>Что даёт участие</h3>
        <ul>
          {e.results.map((r) => (
            <li key={r}>{r}</li>
          ))}
        </ul>
        <h3>Требования к участникам</h3>
        <p>
          {e.grades.join(", ")} классы · {e.participation}
        </p>
        <p>
          Регионы участников:{" "}
          <em>{e.eligibleRegions.includes("*")
            ? "Все регионы"
            : e.eligibleRegions.join(", ")}</em>
        </p>
        <p>
          Доступно для ОВЗ: <em>{bool(e.accessible)}</em>
          <br />
          Согласие родителей: <em>{bool(e.parentalConsent)}</em>
        </p>
      </section>
      <section className="glass details-card">
        <h2>Когда и где</h2>
        <dl>
          <dt>Формат и место</dt>
          <dd>
            {e.format} · {e.region}
          </dd>
          <dt>Приём заявок</dt>
          <dd>
            {dateLabel(e.opens)} — {dateLabel(e.deadline)}
          </dd>
          <dt>Проведение</dt>
          <dd>
            {dateLabel(e.start)} — {dateLabel(e.end)}
          </dd>
          <dt>Стоимость</dt>
          <dd>
            {e.cost}
            {e.price > 0 ? ` · ${e.price.toLocaleString("ru")} ₽` : ""}
          </dd>
          <dt>Как попасть</dt>
          <dd>{e.admission}</dd>
          <dt>Уровень / организатор</dt>
          <dd>
            {e.level} · {e.organizerType}
          </dd>
          <dt>Направление</dt>
          <dd>{e.direction}</dd>
          <dt>Проверено платформой</dt>
          <dd>{bool(e.verified)}</dd>
        </dl>
      </section>
      <section className="glass details-card">
        <h2>Особенности программы</h2>
        <dl>
          {SPECIAL[e.type].map((f) => {
            const v = (
              e.special as unknown as Record<
                string,
                string | number | boolean | undefined
              >
            )[f.key];
            return (
              <div key={f.key}>
                <dt>{f.label}</dt>
                <dd>{v === undefined ? "Не указано" : valueLabel(v)}</dd>
              </div>
            );
          })}
        </dl>
      </section>
      <section className="details-actions" aria-label="Действия с мероприятием">
        <button
          className={`primary${isParticipating ? " is-participating" : ""}`}
          onClick={continueToOpportunity}
        >
          {isParticipating ? "Участвую" : "Перейти к регистрации"}
        </button>
        <button className="details-calendar-link" onClick={onGoToCalendar}>
          Перейти в календарь <span aria-hidden="true">→</span>
        </button>
        {registrationNotice && !registrationUrl && (
          <p className="details-notice" role="status">
            Ссылка на страницу мероприятия ещё не указана.
          </p>
        )}
      </section>
    </main>
  );
}
