// Centralized API error model. The backend returns FastAPI's `{ "detail": ... }`
// shape; we normalize everything axios throws into a single ApiError so the UI
// can render a friendly message without re-deriving the structure each time.
import { AxiosError } from 'axios';

export class ApiError extends Error {
  readonly status: number;
  /** Machine-readable, when the backend provides one (else mirrors message). */
  readonly code: string;

  constructor(message: string, status: number, code?: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code ?? message;
  }

  get isAuth(): boolean {
    return this.status === 401;
  }
  get isForbidden(): boolean {
    return this.status === 403;
  }
  get isNotFound(): boolean {
    return this.status === 404;
  }
}

interface DetailBody {
  detail?: string | { msg?: string }[] | Record<string, unknown>;
}

/** Pull a human message out of a FastAPI error body. */
function extractDetail(data: unknown, fallback: string): string {
  if (!data || typeof data !== 'object') return fallback;
  const detail = (data as DetailBody).detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg;
  return fallback;
}

export function toApiError(err: unknown): ApiError {
  if (err instanceof ApiError) return err;
  if (err instanceof AxiosError) {
    const status = err.response?.status ?? 0;
    if (status === 0) {
      return new ApiError('Network error — please check your connection.', 0, 'network');
    }
    return new ApiError(extractDetail(err.response?.data, err.message), status);
  }
  if (err instanceof Error) return new ApiError(err.message, 0);
  return new ApiError('Something went wrong.', 0);
}
