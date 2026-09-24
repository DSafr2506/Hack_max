import { DEMO_EVENTS, DEMO_TODAY } from "../data/mock";
import type { Opportunity } from "../types";
export type DemoMode = "normal" | "loading" | "error" | "empty";
export interface OpportunityService {
  list(mode: DemoMode, signal?: AbortSignal): Promise<Opportunity[]>;
}
export const clock = { today: () => DEMO_TODAY };
export const opportunityService: OpportunityService = {
  async list(mode, signal) {
    await new Promise<void>((resolve, reject) => {
      const abort = () => {
        clearTimeout(timer);
        reject(new DOMException("Aborted", "AbortError"));
      };
      const timer = setTimeout(
        () => {
          signal?.removeEventListener("abort", abort);
          resolve();
        },
        mode === "loading" ? 5000 : 400,
      );
      if (signal?.aborted) abort();
      else signal?.addEventListener("abort", abort, { once: true });
    });
    if (mode === "error") throw new Error("Демонстрационная ошибка загрузки");
    return mode === "empty" ? [] : DEMO_EVENTS;
  },
};
