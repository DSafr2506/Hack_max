import { useState } from "react";
import type { EventType, Grade, Profile } from "../types";
import { CITIES, TYPES } from "../data/catalog";
import { Choice, Primary } from "../components/ui";
import { toggle } from "../state/filters";
export function Onboarding({
  profile,
  onChange,
  onComplete,
  onCancel,
  editing = false,
}: {
  profile: Profile;
  onChange: (p: Profile) => void;
  onComplete: () => void;
  onCancel?: () => void;
  editing?: boolean;
}) {
  const [step, setStep] = useState(editing ? 1 : 0);
  const [search, setSearch] = useState("");
  const titles = [
    "Агрегатор возможностей\nдля учеников",
    "Выберите ваш\nкласс обучения",
    "В каком городе\nвы обучаетесь?",
    "Какие возможности\nвам интересны?",
    "Какие у вас цели\nна этот год?",
  ];
  const valid =
    step === 1
      ? !!profile.grade
      : step === 2
        ? !!profile.cityId
        : step === 3
          ? profile.types.length > 0
          : true;
  const cities = CITIES.filter((c) =>
    c.name
      .toLocaleLowerCase("ru")
      .includes(search.trim().toLocaleLowerCase("ru")),
  );
  function go(n: number) {
    setStep(n);
    window.scrollTo(0, 0);
  }
  return (
    <main className={`onboarding step-${step}`}>
      <header className="onboard-header">
        {step > 0 ? (
          <button
            className="back"
            onClick={() => go(step - 1)}
            aria-label="Предыдущий шаг"
          >
            ←
          </button>
        ) : (
          <span />
        )}
        <span>Агрегатор возможностей</span>
        {onCancel ? (
          <button onClick={onCancel} aria-label="Отменить редактирование">
            ✕
          </button>
        ) : (
          <span />
        )}
      </header>
      {step > 0 && (
        <div className="steps" aria-label={`Шаг ${step} из 4`}>
          {[1, 2, 3, 4].map((s) => (
            <span key={s} className={s <= step ? "active" : ""} />
          ))}
        </div>
      )}
      <section className="onboard-body">
        {step === 0 && (
          <div className="welcome-mark" aria-hidden="true">
            ✦
          </div>
        )}
        <h1>{titles[step]}</h1>
        {step === 0 ? (
          <div className="benefits">
            <p>
              <span>⌕</span>Находите олимпиады, хакатоны и другие возможности в
              одном месте
            </p>
            <p>
              <span>♡</span>Получайте подборки с учётом вашего города, класса,
              интересов и целей
            </p>
            <p>
              <span>↗</span>Выбирайте свою цель и открывайте новые возможности
            </p>
          </div>
        ) : step === 1 ? (
          <div className="choices">
            {([8, 9, 10, 11] as Grade[]).map((g) => (
              <Choice
                key={g}
                selected={profile.grade === g}
                onClick={() => onChange({ ...profile, grade: g })}
              >
                {g} класс
              </Choice>
            ))}
          </div>
        ) : step === 2 ? (
          <div className="city-panel">
            <label className="search-label">
              Поиск по названию города
              <input
                autoComplete="off"
                type="search"
                value={search}
                placeholder="Начните вводить город"
                onChange={(e) => setSearch(e.target.value)}
              />
            </label>
            <div className="city-list">
              {cities.length ? (
                cities.map((c) => (
                  <Choice
                    key={c.id}
                    selected={profile.cityId === c.id}
                    onClick={() => onChange({ ...profile, cityId: c.id })}
                  >
                    <span>
                      {c.name}
                      <small>{c.region}</small>
                    </span>
                  </Choice>
                ))
              ) : (
                <p role="status">
                  Ничего не найдено. Попробуйте другое название.
                </p>
              )}
            </div>
            {profile.cityId && (
              <small>
                Выбрано: {CITIES.find((c) => c.id === profile.cityId)?.name}
              </small>
            )}
          </div>
        ) : step === 3 ? (
          <>
            <div className="choices">
              {(Object.keys(TYPES) as EventType[]).map((t) => (
                <Choice
                  key={t}
                  selected={profile.types.includes(t)}
                  onClick={() =>
                    onChange({ ...profile, types: toggle(profile.types, t) })
                  }
                >
                  {TYPES[t]}
                </Choice>
              ))}
            </div>
            <p className="hint">Можно выбрать несколько, минимум один</p>
          </>
        ) : (
          <div className="goal-input">
            <label htmlFor="goal">
              Напишите свои цели <small>Необязательно</small>
            </label>
            <textarea
              id="goal"
              value={profile.goalText}
              maxLength={500}
              rows={4}
              placeholder="Например, попробовать себя в программировании"
              onChange={(e) =>
                onChange({ ...profile, goalText: e.target.value })
              }
            />
            <small>
              {profile.goalText.length} / 500 · Сохранится в профиле
            </small>
          </div>
        )}
      </section>
      <footer className="onboard-footer">
        <Primary
          disabled={!valid}
          onClick={() => (step === 4 ? onComplete() : go(step + 1))}
        >
          {step === 0
            ? "Приступить"
            : step === 4
              ? editing
                ? "Сохранить"
                : "Открыть возможности"
              : "Далее"}
        </Primary>
        <small>Демонстрационный режим · 8–11 классы</small>
      </footer>
    </main>
  );
}
