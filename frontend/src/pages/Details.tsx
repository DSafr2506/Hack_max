import { useEffect, useState } from "react";
import type { Opportunity } from "../types";
import { SPECIAL, TYPES, valueLabel } from "../data/catalog";
import { dateLabel } from "../components/ui";
import { absolute, api, hasSession } from "../services/api";
import {
  bindBackButton,
  download,
  hapticSuccess,
  insideMax,
  openExternal,
  share,
} from "../integration/max";
export function Details({
  event: e,
  onBack,
  onChange,
  demo = false,
}: {
  event: Opportunity;
  onBack: () => void;
  onChange?: (e: Opportunity) => void;
  demo?: boolean;
}) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  useEffect(() => bindBackButton(onBack), [onBack]);
  const bool = (v: boolean | undefined) =>
    v === undefined ? "Не указано" : v ? "Да" : "Нет";
  const going = e.myStatus === "going";
  const fromBackend = e.backendId !== undefined;

  async function participate(status: "going" | "skipped") {
    if (!e.backendId) return;
    if (!hasSession()) {
      setMessage("Откройте приложение из чата с ботом в MAX, чтобы отмечать участие.");
      return;
    }
    setBusy(true);
    try {
      await api.participate(e.backendId, status);
      onChange?.({ ...e, myStatus: status });
      if (status === "going") {
        hapticSuccess();
        setMessage("Добавили в «Мои даты». Бот напомнит о дедлайне в MAX.");
      } else setMessage("Убрали из «Моих дат», напоминаний не будет.");
    } catch {
      setMessage("Не получилось. Попробуйте ещё раз.");
    } finally {
      setBusy(false);
    }
  }
  async function onShare() {
    if (!e.slug || !hasSession()) return;
    try {
      const s = await api.share(e.slug);
      await share(e.title, s.deep_link, s.share_url);
    } catch {
      setMessage("Не получилось подготовить ссылку.");
    }
  }
  return (
    <main className="page details">
      {!insideMax() && <button onClick={onBack}>← К подборке</button>}
      <p className="eyebrow">{TYPES[e.type]}</p>
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
            {e.hasDeadline === false
              ? e.registrationChannel === "school"
                ? "Через школу"
                : "Уточняйте у организатора"
              : e.opens > "2000-01-01"
                ? `${dateLabel(e.opens)} — ${dateLabel(e.deadline)}`
                : `до ${dateLabel(e.deadline)}`}
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
          <dt>Проверено</dt>
          <dd>
            {e.verifiedAt ? dateLabel(e.verifiedAt.slice(0, 10)) : bool(e.verified)}
          </dd>
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
      {e.benefitNote && (
        <section className="glass">
          <h2>Что пишет организатор</h2>
          <p>{e.benefitNote}</p>
        </section>
      )}
      {fromBackend ? (
        <>
          <p className="hint">
            Условия — как у организатора, льгот мы не обещаем. Источник:{" "}
            <a
              href={e.source}
              onClick={(ev) => {
                ev.preventDefault();
                if (e.source) openExternal(e.source);
              }}
            >
              {e.sourceName || e.source}
            </a>
            {e.freshness === "reported" && " · школьники сообщили, что данные устарели"}
          </p>
          {message && (
            <p className="notice" role="status">
              {message}
            </p>
          )}
          <div className="detail-actions">
            {going ? (
              <button disabled={busy} onClick={() => participate("skipped")}>
                ✓ Вы участвуете · отменить
              </button>
            ) : (
              <button className="primary" disabled={busy} onClick={() => participate("going")}>
                Участвую
              </button>
            )}
            {e.hasRegistration && e.goUrl ? (
              <button onClick={() => openExternal(absolute(`${e.goUrl}?src=card`))}>
                Перейти к регистрации ↗
              </button>
            ) : (
              <p className="hint">Регистрация через школу — спросите учителя предмета.</p>
            )}
            <div className="reset-row">
              {hasSession() && (
                <button className="text-button" onClick={onShare}>
                  Поделиться
                </button>
              )}
              {e.slug && (
                <button
                  className="text-button"
                  onClick={() => download(absolute(`/api/events/${e.slug}.ics`), `${e.slug}.ics`)}
                >
                  В календарь
                </button>
              )}
              {demo && hasSession() && e.backendId && (
                <button
                  className="text-button"
                  onClick={() =>
                    api
                      .demoReminder(e.backendId!)
                      .then(() => setMessage("Напоминание придёт в MAX в течение 30 секунд."))
                      .catch(() => setMessage("Не удалось поставить напоминание."))
                  }
                >
                  Демо-напоминание
                </button>
              )}
            </div>
          </div>
        </>
      ) : e.source && /^https:\/\//.test(e.source) ? (
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
