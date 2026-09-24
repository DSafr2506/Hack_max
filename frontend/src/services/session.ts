// Запуск приложения: справочники с бэкенда и вход через MAX.
import { applyBackendDicts } from "../data/catalog";
import { api, setRegionNames, type BackendUser } from "./api";
import { initData, insideMax, ready, startParam } from "../integration/max";

let subjects: Record<string, string> = {};
export const subjectNames = () => subjects;

export type Session = {
  user: BackendUser | null; // null — вход не выполнен (браузер без dev-режима или ошибка)
  startParam: string | null;
  demo: boolean;
  offline: boolean; // бэкенд недоступен
};

export async function boot(): Promise<Session> {
  ready();
  const query = new URLSearchParams(location.search);
  const devUser = query.get("dev");
  let offline = false;
  try {
    const dicts = await api.dicts();
    applyBackendDicts(dicts);
    setRegionNames(dicts);
    subjects = Object.fromEntries(dicts.subject.map((s) => [s.code, s.name]));
  } catch {
    offline = true;
  }

  let user: BackendUser | null = null;
  let param = startParam();
  if (!offline && (insideMax() || devUser)) {
    try {
      // В MAX — подписанная initData. В браузере — ?dev=<имя> (работает, только если на бэкенде DEV_FAKE_AUTH=1)
      const r = await api.launch(insideMax() ? { init_data: initData() } : { dev_user_id: devUser! });
      user = r.user;
      param = r.start_param ?? param;
    } catch {
      user = null;
    }
  }
  const demo = param === "demo" || query.has("demo");
  return { user, startParam: param, demo, offline };
}
