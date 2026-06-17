import type { Bootstrap, User } from "./types";

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

type ApiOptions = RequestInit & {
  token?: string | null;
};

export class UnauthorizedError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "UnauthorizedError";
  }
}

export async function api<T>(path: string, options: ApiOptions = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (!headers.has("Content-Type") && options.body) {
    headers.set("Content-Type", "application/json");
  }
  if (options.token) {
    headers.set("Authorization", `Bearer ${options.token}`);
  }
  const response = await fetch(`${API_BASE}/api${path}`, {
    ...options,
    headers
  });
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    const message = typeof payload === "object" && payload && "detail" in payload ? String(payload.detail) : "Request failed";
    if (response.status === 401) throw new UnauthorizedError(message);
    throw new Error(message);
  }
  return payload as T;
}

export function login(email: string, password: string) {
  return api<{ ok: boolean; token: string; user: User }>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password })
  });
}

export function loadBootstrap(token: string) {
  return api<Bootstrap>("/bootstrap", { token });
}
