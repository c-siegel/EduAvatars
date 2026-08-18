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

// FastAPI antwortet je nach Fehlerart unterschiedlich: HTTPException liefert {detail: "Text"},
// eine Pydantic-Validierung {detail: [{msg, loc}, …]}. Beides wird hier auf einen anzeigbaren Satz
// reduziert, damit Formulare die echte Ursache nennen können statt nur "fehlgeschlagen".
export function errorMessage(error: unknown, fallback: string): string {
  if (!(error instanceof ApiError)) return fallback;
  try {
    const detail = JSON.parse(error.message).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      const messages = detail.map((item) => String(item?.msg ?? "").replace(/^Value error, /, "")).filter(Boolean);
      if (messages.length) return messages.join(" ");
    }
  } catch {
    // Kein JSON-Body (z.B. Proxy-/Netzwerkfehler) — dann bleibt es beim Fallback.
  }
  return fallback;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    throw new ApiError(res.status, await res.text());
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const apiClient = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
  put: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PUT", body: body ? JSON.stringify(body) : undefined }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
  // Kein Content-Type-Header hier — der Browser setzt bei FormData selbst den
  // multipart/form-data-Header inkl. Boundary (z.B. für den Avatar-Upload in 1e).
  upload: <T>(path: string, formData: FormData) =>
    request<T>(path, { method: "POST", headers: {}, body: formData }),
};
