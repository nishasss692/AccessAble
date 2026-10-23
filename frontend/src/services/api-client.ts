/**
 * Base API Client configured with VITE_API_BASE_URL.
 */

const RAW_API_BASE_URL = import.meta.env.VITE_API_BASE_URL as string | undefined;
export const API_BASE_URL = (RAW_API_BASE_URL || 'http://localhost:8000').replace(/\/+$/, '');
export const API_V1 = `${API_BASE_URL}/api/v1`;

export class ApiRequestError extends Error {
  status: number;
  data: unknown;

  constructor(message: string, status: number, data: unknown) {
    super(message);
    this.name = 'ApiRequestError';
    this.status = status;
    this.data = data;
  }
}

export async function apiClient<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = endpoint.startsWith('http') ? endpoint : `${API_V1}${endpoint.startsWith('/') ? '' : '/'}${endpoint}`;

  const headers = new Headers(options.headers || {});
  if (!headers.has('Content-Type') && options.body && typeof options.body === 'string') {
    headers.set('Content-Type', 'application/json');
  }
  if (!headers.has('Accept')) {
    headers.set('Accept', 'application/json');
  }

  let response: Response;
  try {
    response = await fetch(url, {
      ...options,
      headers,
    });
  } catch (error) {
    throw new ApiRequestError(
      'Unable to connect to AccessAble backend. Please ensure the server is running.',
      0,
      error
    );
  }

  if (!response.ok) {
    let errorDetail = `Request failed with status ${response.status}`;
    let errorPayload: unknown = null;
    try {
      errorPayload = await response.json();
      if (typeof errorPayload === 'object' && errorPayload !== null && 'detail' in errorPayload) {
        const detail = (errorPayload as { detail: unknown }).detail;
        if (typeof detail === 'string') {
          errorDetail = detail;
        } else if (Array.isArray(detail)) {
          errorDetail = detail.map((d: { msg?: string }) => d.msg || JSON.stringify(d)).join(', ');
        }
      }
    } catch {
      // not JSON
    }
    throw new ApiRequestError(errorDetail, response.status, errorPayload);
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return {} as T;
  }

  return response.json() as Promise<T>;
}
