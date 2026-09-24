import { useEffect, useState } from "react";
import { absolute, api, hasSession, mskDate, sessionToken, type CalendarItem } from "../services/api";
import { download } from "../integration/max";
import { dateLabel } from "./ui";

/** «Мои даты»: дедлайны и старты мероприятий, где нажато «Участвую». */
export function MyDates({ onOpen }: { onOpen: (eventId: number) => void }) {
  const [items, setItems] = useState<CalendarItem[] | null>(null);
  useEffect(() => {
    if (!hasSession()) return;
    api
      .calendar()
      .then((all) => setItems(all.filter((i) => Date.parse(i.at) > Date.now() - 86_400_000)))
      .catch(() => setItems([]));
  }, []);
  if (!hasSession()) return null;
  return (
    <section className="glass my-dates">
      <h2>Мои даты</h2>
      {items === null ? (
        <p>Загружаем…</p>
      ) : !items.length ? (
        <p>
          Пока пусто. Нажмите «Участвую» в карточке мероприятия — даты появятся
          здесь, а бот напомнит о дедлайне.
        </p>
      ) : (
        <>
          <ul>
            {items.map((i) => (
              <li key={`${i.event_id}-${i.kind}`}>
                <button className="text-button" onClick={() => onOpen(i.event_id)}>
                  <strong>{dateLabel(mskDate(i.at))}</strong> ·{" "}
                  {i.kind === "deadline" ? "дедлайн регистрации" : "начало"} —{" "}
                  {i.title}
                </button>
              </li>
            ))}
          </ul>
          <button
            onClick={() =>
              download(
                absolute(`/api/me/calendar.ics?token=${encodeURIComponent(sessionToken() ?? "")}`),
                "my-dates.ics",
              )
            }
          >
            Экспорт в календарь телефона
          </button>
        </>
      )}
    </section>
  );
}
