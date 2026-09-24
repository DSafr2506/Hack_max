import type { Opportunity } from "../types";
import { SPECIAL, TYPES, valueLabel } from "../data/catalog";
import { dateLabel } from "../components/ui";
export function Details({
  event: e,
  onBack,
}: {
  event: Opportunity;
  onBack: () => void;
}) {
  const bool = (v: boolean | undefined) =>
    v === undefined ? "Не указано" : v ? "Да" : "Нет";
  return (
    <main className="page details">
      <button onClick={onBack}>← К подборке</button>
      <p className="eyebrow">{TYPES[e.type]} · Демо</p>
      <h1>{e.title}</h1>
      <p>{e.organizer}</p>
      <section className="glass">
        <h2>О мероприятии</h2>
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
          {e.eligibleRegions.includes("*")
            ? "Все регионы"
            : e.eligibleRegions.join(", ")}
        </p>
        <p>
          Доступно для ОВЗ: {bool(e.accessible)}
          <br />
          Согласие родителей: {bool(e.parentalConsent)}
        </p>
      </section>
      <section className="glass">
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
          <dt>Длительность</dt>
          <dd>{e.duration} дн.</dd>
          <dt>Стоимость</dt>
          <dd>
            {e.cost}
            {e.price > 0 ? ` · ${e.price.toLocaleString("ru")} ₽` : ""}
          </dd>
          <dt>Проезд оплачивается</dt>
          <dd>{bool(e.travel)}</dd>
          <dt>Проживание оплачивается</dt>
          <dd>{bool(e.accommodation)}</dd>
          <dt>Как попасть</dt>
          <dd>{e.admission}</dd>
          <dt>Уровень / организатор</dt>
          <dd>
            {e.level} · {e.organizerType}
          </dd>
          <dt>Направление</dt>
          <dd>{e.direction}</dd>
          <dt>Проверено платформой (демо)</dt>
          <dd>{bool(e.verified)}</dd>
        </dl>
      </section>
      <section className="glass">
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
      {e.source && /^https:\/\//.test(e.source) ? (
        <a className="primary" href={e.source} target="_blank" rel="noreferrer">
          Официальный источник ↗
        </a>
      ) : (
        <p className="notice">
          Это вымышленное демонстрационное мероприятие. Настоящей ссылки и
          приёма заявок нет.
        </p>
      )}
    </main>
  );
}
