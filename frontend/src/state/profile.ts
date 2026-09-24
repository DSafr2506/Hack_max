import type { Profile } from "../types";
import { CITIES, TYPES } from "../data/catalog";
export const PROFILE_KEY = "max-opportunities.profile.v1";
export const blankProfile = (): Profile => ({
  grade: null,
  cityId: "",
  types: [],
  goalText: "",
  completed: false,
});
export function readProfile(storage: Pick<Storage, "getItem">): Profile {
  try {
    const raw = storage.getItem(PROFILE_KEY);
    if (!raw) return blankProfile();
    const p = JSON.parse(raw);
    if (
      !p ||
      ![null, 8, 9, 10, 11].includes(p.grade) ||
      typeof p.cityId !== "string" ||
      (p.cityId && !CITIES.some((c) => c.id === p.cityId)) ||
      !Array.isArray(p.types) ||
      !p.types.every(
        (t: unknown) => typeof t === "string" && Object.hasOwn(TYPES, t),
      ) ||
      new Set(p.types).size !== p.types.length ||
      typeof p.goalText !== "string" ||
      p.goalText.length > 500 ||
      typeof p.completed !== "boolean" ||
      (p.completed && (!p.grade || !p.cityId || !p.types.length))
    )
      return blankProfile();
    return {
      grade: p.grade,
      cityId: p.cityId,
      types: p.types,
      goalText: p.goalText,
      completed: p.completed,
    };
  } catch {
    return blankProfile();
  }
}
export function saveProfile(storage: Pick<Storage, "setItem">, p: Profile) {
  try {
    storage.setItem(PROFILE_KEY, JSON.stringify(p));
    return true;
  } catch {
    return false;
  }
}
export function loadBrowserProfile() {
  try {
    return readProfile(window.localStorage);
  } catch {
    return blankProfile();
  }
}
export function saveBrowserProfile(p: Profile) {
  try {
    return saveProfile(window.localStorage, p);
  } catch {
    return false;
  }
}
