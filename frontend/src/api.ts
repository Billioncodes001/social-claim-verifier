import { QueryClient, useQuery } from "@tanstack/react-query";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, staleTime: 10_000, refetchOnWindowFocus: false },
  },
});
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}
export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch("/api" + path, {
    ...options,
    headers: { "Content-Type": "application/json", ...options.headers },
  });
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    if (response.status === 401 && !path.startsWith("/auth"))
      window.dispatchEvent(new Event("session-expired"));
    const detail = body?.detail;
    throw new ApiError(
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((x: { msg: string }) => x.msg).join(". ")
          : "The request could not be completed. Please try again.",
      response.status,
    );
  }
  return body as T;
}
export function send<T = { ok: boolean }>(
  path: string,
  body: unknown = {},
  method = "POST",
) {
  return api<T>(path, { method, body: JSON.stringify(body) });
}
export function useResource<T>(path: string, interval?: number) {
  return useQuery<T>({
    queryKey: [path],
    queryFn: () => api<T>(path),
    refetchInterval: interval,
  });
}
export const refresh = () => queryClient.invalidateQueries();
export const navigate = (route: string) => {
  window.location.hash = route;
};
export const field = (form: FormData, key: string) =>
  String(form.get(key) ?? "").trim();
export const lines = (form: FormData, key = "evidence") =>
  field(form, key)
    .split("\n")
    .map((x) => x.trim())
    .filter(Boolean);
export const stamp = (value?: string | null) =>
  value
    ? new Date(value).toLocaleString(undefined, {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "Not yet";
export const safeUrl = (value?: string) =>
  /^https?:\/\//i.test(value || "") ? value : undefined;
