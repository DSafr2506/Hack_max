import { useEffect, useRef, useState } from "react";
import type { EventType, Field, Filters, Profile, Value } from "../types";
import { GROUPS, SPECIAL, TYPES, valueLabel } from "../data/catalog";
import {
  changeTypes,
  emptyFilters,
  profileFilters,
  toggle,
  validateFilters,
} from "../state/filters";
import { Choice } from "./ui";
export function FilterSheet({
  filters,
  profile,
  onClose,
  onApply,
}: {
  filters: Filters;
  profile: Profile;
  onClose: () => void;
  onApply: (f: Filters) => void;
}) {
  const [draft, setDraft] = useState<Filters>(() => structuredClone(filters));
  const dialog = useRef<HTMLDialogElement>(null);
  const error = validateFilters(draft);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement;
    const el = dialog.current!;
    el.showModal();
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      el.close();
      document.body.style.overflow = overflow;
      previous?.focus();
    };
  }, []);
  function field(field: Field, special = false) {
    const values = special ? draft.special : draft.values;
    const ranges = special ? draft.specialRanges : draft.ranges;
    const updateValues = (v: Value[]) =>
      setDraft({
        ...draft,
        [special ? "special" : "values"]: { ...values, [field.key]: v },
      });
    return (
      <fieldset key={field.key}>
        <legend>{field.label}</legend>
        {field.kind === "date" || field.kind === "number" ? (
          <div className="range">
            {(["min", "max"] as const).map((bound) => (
              <label key={bound}>
                {bound === "min" ? "От" : "До"}
                <input
                  aria-label={`${field.label}: ${bound === "min" ? "от" : "до"}`}
                  type={field.kind === "date" ? "date" : "number"}
                  min={field.kind === "number" ? 0 : undefined}
                  step={field.kind === "number" ? 1 : undefined}
                  value={ranges[field.key]?.[bound] ?? ""}
                  onChange={(e) =>
                    setDraft({
                      ...draft,
                      [special ? "specialRanges" : "ranges"]: {
                        ...ranges,
                        [field.key]: {
                          ...ranges[field.key],
                          [bound]: e.target.value,
                        },
                      },
                    })
                  }
                />
              </label>
            ))}
          </div>
        ) : field.kind === "boolean" ? (
          <select
            aria-label={field.label}
            value={
              values[field.key]?.length ? String(values[field.key][0]) : ""
            }
            onChange={(e) =>
              updateValues(
                e.target.value === "" ? [] : [e.target.value === "true"],
              )
            }
          >
            <option value="">Не ограничивать</option>
            <option value="true">Да</option>
            <option value="false">Нет</option>
          </select>
        ) : (
          <div className="chips">
            {field.options?.map((v) => (
              <Choice
                key={String(v)}
                selected={values[field.key]?.includes(v) ?? false}
                onClick={() => updateValues(toggle(values[field.key] ?? [], v))}
              >
                {valueLabel(v)}
              </Choice>
            ))}
          </div>
        )}
      </fieldset>
    );
  }
  return (
    <dialog
      ref={dialog}
      className="sheet"
      aria-labelledby="filters-title"
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="sheet-layout">
        <header>
          <div>
            <small>НАСТРОЙТЕ ПОДБОРКУ</small>
            <h2 id="filters-title">Все фильтры</h2>
          </div>
          <button aria-label="Закрыть фильтры" onClick={onClose}>
            ✕
          </button>
        </header>
        <div className="sheet-content">
          <button
            className="text-button"
            onClick={() => setDraft(profileFilters(profile))}
          >
            По моему профилю
          </button>
          <fieldset>
            <legend>Тип мероприятия</legend>
            <div className="chips">
              {(Object.keys(TYPES) as EventType[]).map((t) => (
                <Choice
                  key={t}
                  selected={draft.types.includes(t)}
                  onClick={() =>
                    setDraft(changeTypes(draft, toggle(draft.types, t)))
                  }
                >
                  {TYPES[t]}
                </Choice>
              ))}
            </div>
          </fieldset>
          <Choice
            selected={draft.regionOnly}
            onClick={() =>
              setDraft({ ...draft, regionOnly: !draft.regionOnly })
            }
          >
            Доступно из моего региона
          </Choice>
          {GROUPS.map((group) => (
            <section key={group.label}>
              <h3>{group.label}</h3>
              {group.fields.map((f) => field(f))}
            </section>
          ))}
          {draft.types.length === 1 && (
            <section>
              <h3>{TYPES[draft.types[0]]}: особенности</h3>
              {SPECIAL[draft.types[0]].map((f) => field(f, true))}
            </section>
          )}
        </div>
        <footer>
          {error && <p role="alert">{error}</p>}
          <div className="sheet-actions">
            <button onClick={() => setDraft(emptyFilters())}>Сбросить</button>
            <button
              className="primary"
              disabled={!!error}
              onClick={() => onApply(draft)}
            >
              Применить
            </button>
          </div>
        </footer>
      </div>
    </dialog>
  );
}
