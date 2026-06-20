/**
 * Thin fetch wrapper around the FastAPI backend.
 *
 * - `credentials: 'include'` sends the HttpOnly auth cookie on every request.
 * - Non-2xx responses throw `ApiError` carrying the status + parsed body.
 * - JSON in, JSON out; pass `FormData` directly for file uploads.
 */

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export class ApiError extends Error {
  constructor(
    public status: number,
    public body: unknown,
  ) {
    super(`API ${status}`)
    this.name = 'ApiError'
  }
}

type Options = Omit<RequestInit, 'body'> & { body?: unknown }

async function request<T>(path: string, options: Options = {}): Promise<T> {
  const { body, headers, ...rest } = options
  const isForm = body instanceof FormData

  const res = await fetch(`${BASE_URL}${path}`, {
    ...rest,
    credentials: 'include',
    headers: {
      ...(isForm ? {} : { 'Content-Type': 'application/json' }),
      ...headers,
    },
    body: isForm ? body : body !== undefined ? JSON.stringify(body) : undefined,
  })

  const payload = res.status === 204 ? null : await res.json().catch(() => null)
  if (!res.ok) throw new ApiError(res.status, payload)
  return payload as T
}

export const api = {
  get: <T>(path: string) => request<T>(path, { method: 'GET' }),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'POST', body }),
  put: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'PUT', body }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'PATCH', body }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
}
