// Public guest service — no auth. Uses only existing /guest/* endpoints.
import type { AxiosProgressEvent } from 'axios';
import api, { httpGet } from '@/lib/api';
import { toApiError } from '@/lib/errors';
import type { GuestEvent, SelfieMatchResult } from '@/types/models';

export function getGuestEvent(slug: string): Promise<GuestEvent> {
  return httpGet<GuestEvent>(`/guest/${slug}`);
}

/** POST selfie + consent → matched photos (single synchronous call). */
export async function submitSelfie(
  slug: string,
  blob: Blob,
  opts?: { signal?: AbortSignal; onUploadProgress?: (e: AxiosProgressEvent) => void },
): Promise<SelfieMatchResult> {
  const form = new FormData();
  form.append('file', blob, 'selfie.jpg');
  form.append('consent', 'true');
  try {
    const res = await api.post<SelfieMatchResult>(`/guest/${slug}/selfie`, form, {
      signal: opts?.signal,
      onUploadProgress: opts?.onUploadProgress,
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data;
  } catch (e) {
    throw toApiError(e);
  }
}

/** Backend serves local files relative to its host; S3 urls are absolute. */
export function absoluteUrl(url: string): string {
  if (!url) return url;
  if (/^https?:\/\//.test(url)) return url;
  const base = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api').replace(/\/api\/?$/, '');
  return `${base}${url}`;
}

export async function getDownloadUrl(slug: string, photoId: number): Promise<string> {
  const data = await httpGet<{ url: string; expires_in: number }>(`/guest/${slug}/photos/${photoId}/download`);
  return absoluteUrl(data.url);
}

export async function downloadAllZip(slug: string, photoIds: number[]): Promise<void> {
  const res = await api.post(`/guest/${slug}/download-zip`, { photo_ids: photoIds }, { responseType: 'blob' });
  const url = URL.createObjectURL(res.data as Blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${slug}-photos.zip`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
