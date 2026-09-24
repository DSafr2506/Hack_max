import type { Opportunity } from "../types";
import { refreshOptionsFromEvents } from "../data/catalog";
import { api, mskDate, toOpportunity } from "./api";
import { subjectNames } from "./session";

export type DemoMode = "normal" | "loading" | "error" | "empty";
export interface OpportunityService {
  list(mode: DemoMode, signal?: AbortSignal): Promise<Opportunity[]>;
}

/** Сегодня по Москве: дедлайны и напоминания бэкенд тоже считает по МСК. */
export const clock = { today: () => mskDate(new Date()) };

const wait = (ms: number, signal?: AbortSignal) =>
  new Promise<void>((resolve, reject) => {
    const abort = () => {
      clearTimeout(timer);
      reject(new DOMException("Aborted", "AbortError"));
    };
    const timer = setTimeout(() => {
      signal?.removeEventListener("abort", abort);
      resolve();
    }, ms);
    if (signal?.aborted) abort();
    else signal?.addEventListener("abort", abort, { once: true });
  });

/** Мероприятия с бэкенда (GET /api/events?detail=full). Режимы loading/error/empty — для показа состояний на демо. */
export const opportunityService: OpportunityService = {
  async list(mode, signal) {
    if (mode === "loading") await wait(5000, signal);
    if (mode === "error") throw new Error("Демонстрационная ошибка загрузки");
    if (mode === "empty") return [];
    const { items } = await api.events(signal);
    const names = subjectNames();
    const events = items
      .map((e) => toOpportunity(e, names))
      .filter((e): e is Opportunity => e !== null);
    refreshOptionsFromEvents(events as unknown as Parameters<typeof refreshOptionsFromEvents>[0]);
    return events;
  },
};
