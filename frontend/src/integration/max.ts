// Граница интеграции с MAX. Методы — по официальной документации MAX Bridge:
// https://dev.max.ru/docs/webapps/bridge (скрипт подключается в index.html).
// Вне MAX (обычный браузер) всё работает через фолбэки.

type WebAppApi = {
  initData?: string;
  initDataUnsafe?: { start_param?: string };
  platform?: string;
  ready?: () => void;
  openLink?: (url: string) => unknown;
  shareMaxContent?: (p: { text?: string; link?: string }) => Promise<unknown>;
  downloadFile?: (url: string, fileName: string) => Promise<unknown>;
  BackButton?: {
    show: () => void;
    hide: () => void;
    onClick: (cb: () => void) => void;
    offClick: (cb: () => void) => void;
  };
  HapticFeedback?: {
    notificationOccurred?: (type: "error" | "success" | "warning") => void;
  };
};

declare global {
  interface Window {
    WebApp?: WebAppApi;
  }
}

const wa = (): WebAppApi | undefined =>
  typeof window === "undefined" ? undefined : window.WebApp;

export const insideMax = (): boolean => Boolean(wa()?.initData);

export const environment = {
  get name() {
    return insideMax() ? "MAX" : "Браузер";
  },
  get sdkConnected() {
    return insideMax();
  },
};

export function initData(): string {
  return wa()?.initData ?? "";
}

/** Параметр запуска: из MAX или, для отладки в браузере, из ?startapp= */
export function startParam(): string | null {
  return (
    wa()?.initDataUnsafe?.start_param ??
    new URLSearchParams(location.search).get("startapp")
  );
}

export function ready(): void {
  try {
    wa()?.ready?.();
  } catch {
    /* старые клиенты */
  }
}

export function openExternal(url: string): void {
  const api = wa();
  if (api?.openLink) api.openLink(url);
  else window.open(url, "_blank", "noopener");
}

export async function share(text: string, link: string, fallbackUrl: string) {
  try {
    const api = wa();
    if (api?.shareMaxContent) {
      await api.shareMaxContent({ text, link });
      return;
    }
  } catch {
    /* фолбэк ниже */
  }
  openExternal(fallbackUrl);
}

export async function download(url: string, fileName: string) {
  const api = wa();
  try {
    if (api?.downloadFile) {
      await api.downloadFile(url, fileName);
      return;
    }
  } catch {
    /* фолбэк ниже */
  }
  window.open(url, "_blank", "noopener");
}

/** Системная кнопка «назад» MAX. Возвращает функцию отписки. */
export function bindBackButton(handler: () => void): () => void {
  const bb = wa()?.BackButton;
  if (!bb) return () => {};
  bb.onClick(handler);
  bb.show();
  return () => {
    bb.offClick(handler);
    bb.hide();
  };
}

export const hapticSuccess = () =>
  wa()?.HapticFeedback?.notificationOccurred?.("success");
