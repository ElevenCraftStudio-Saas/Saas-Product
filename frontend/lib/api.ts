import axios, { AxiosError, type AxiosRequestConfig, type InternalAxiosRequestConfig } from 'axios';
import { auth } from '@/lib/firebase';
import { toApiError } from '@/lib/errors';

/** Dispatched when a request is unauthorized even after a token refresh. The
 *  SessionGuard provider listens for this and signs the user out cleanly. */
export const SESSION_EXPIRED_EVENT = 'auth:session-expired';

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api',
});

// --- Request: attach a fresh Firebase ID token. Tokens live in the Firebase
//     SDK's own storage (IndexedDB) — never in localStorage. ---
api.interceptors.request.use(async (config: InternalAxiosRequestConfig) => {
  const user = auth?.currentUser;
  if (user) {
    const token = await user.getIdToken(); // cached; refreshed by the SDK as needed
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// --- Response: on a 401, force one token refresh + retry. If it still 401s the
//     session is genuinely expired → broadcast so the app can sign out. ---
interface RetriableConfig extends AxiosRequestConfig {
  _retried?: boolean;
}

api.interceptors.response.use(
  (res) => res,
  async (error: AxiosError) => {
    const original = error.config as (RetriableConfig & InternalAxiosRequestConfig) | undefined;
    const status = error.response?.status;

    if (status === 401 && original && !original._retried && auth?.currentUser) {
      original._retried = true;
      try {
        const fresh = await auth.currentUser.getIdToken(true); // force refresh
        original.headers.Authorization = `Bearer ${fresh}`;
        return api(original);
      } catch {
        // fall through to expiry handling
      }
    }

    if (status === 401 && typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent(SESSION_EXPIRED_EVENT));
    }
    return Promise.reject(error);
  },
);

export default api;

// --- Typed helpers: same axios instance, but they unwrap `.data` and throw a
//     normalized ApiError so callers (services / TanStack Query) get clean types. ---
export async function httpGet<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
  try {
    return (await api.get<T>(url, config)).data;
  } catch (e) {
    throw toApiError(e);
  }
}

export async function httpPost<T>(url: string, body?: unknown, config?: AxiosRequestConfig): Promise<T> {
  try {
    return (await api.post<T>(url, body, config)).data;
  } catch (e) {
    throw toApiError(e);
  }
}

export async function httpPatch<T>(url: string, body?: unknown, config?: AxiosRequestConfig): Promise<T> {
  try {
    return (await api.patch<T>(url, body, config)).data;
  } catch (e) {
    throw toApiError(e);
  }
}

export async function httpDelete<T = void>(url: string, config?: AxiosRequestConfig): Promise<T> {
  try {
    return (await api.delete<T>(url, config)).data;
  } catch (e) {
    throw toApiError(e);
  }
}
