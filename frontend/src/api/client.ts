import i18n from "@/i18n";

// Exportiert für Fälle, in denen eine vom Backend gelieferte relative URL direkt als Browser-Ressource
// gebraucht wird (z.B. <img src>), statt über apiClient zu laufen — z.B. das Profilbild (siehe
// pages/Dashboard/Profile). Backend-URLs sind grundsätzlich router-relativ ohne /api-Präfix
// (analog avatar-models/{id}/file), das Präfix kommt immer erst hier dazu.
export const API_BASE_URL = "/api";
const BASE_URL = API_BASE_URL;

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

// FastAPI antwortet je nach Fehlerart unterschiedlich: HTTPException liefert {detail: "CODE"} oder
// {detail: {code, message}} (siehe app/core/error_codes.py), eine Pydantic-Validierung
// {detail: [{msg: "Value error, CODE", loc}, …]}. In allen Fällen ist `detail` ein stabiler Code,
// keine Anzeigetext — die Übersetzung passiert hier über i18next (errors.<CODE> in
// src/i18n/locales), damit die gleiche Fehlermeldung in beiden Sprachen korrekt ist.
export function errorMessage(error: unknown, fallback: string): string {
  if (!(error instanceof ApiError)) return fallback;
  try {
    const detail = JSON.parse(error.message).detail;
    const code = typeof detail === "string" ? detail : typeof detail === "object" && detail?.code ? detail.code : null;
    if (code) return i18n.t(`errors.${code}`, fallback);
    if (Array.isArray(detail)) {
      const codes = detail
        .map((item) => String(item?.msg ?? "").replace(/^Value error, /, ""))
        .filter(Boolean)
        .map((c) => i18n.t(`errors.${c}`, c));
      if (codes.length) return codes.join(" ");
    }
  } catch {
    // Kein JSON-Body (z.B. Proxy-/Netzwerkfehler) — dann bleibt es beim Fallback.
  }
  return fallback;
}

// Every caller in this codebase passes a plain object (or nothing) — never a Headers instance or
// a tuple array — so a plain Record keeps the merge below simple instead of fighting HeadersInit's
// wider (Headers | string[][] | Record) type.
type SimpleHeaders = Record<string, string>;

async function request<T>(path: string, init?: RequestInit & { headers?: SimpleHeaders }): Promise<T> {
  // Merged (not spread-overwritten) so a caller-supplied `headers` — e.g. the chat-unlock token —
  // doesn't silently drop the default Content-Type. Skipped entirely for a FormData body: the
  // browser has to set that Content-Type itself (multipart boundary), see upload() below.
  const { headers, body, ...restInit } = init ?? {};
  const defaultHeaders: SimpleHeaders = body instanceof FormData ? {} : { "Content-Type": "application/json" };
  const res = await fetch(`${BASE_URL}${path}`, {
    credentials: "include",
    ...restInit,
    body,
    headers: { ...defaultHeaders, ...headers },
  });
  if (!res.ok) {
    throw new ApiError(res.status, await res.text());
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const apiClient = {
  get: <T>(path: string, headers?: SimpleHeaders) => request<T>(path, { headers }),
  post: <T>(path: string, body?: unknown, headers?: SimpleHeaders) =>
    request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined, headers }),
  put: <T>(path: string, body?: unknown, headers?: SimpleHeaders) =>
    request<T>(path, { method: "PUT", body: body ? JSON.stringify(body) : undefined, headers }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
  upload: <T>(path: string, formData: FormData, headers?: SimpleHeaders) =>
    request<T>(path, { method: "POST", body: formData, headers }),
};
