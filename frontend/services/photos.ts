// Photo service — studio upload + per-event listing (require role 'user').
import type { AxiosProgressEvent } from 'axios';
import api from '@/lib/api';
import { toApiError } from '@/lib/errors';
import { httpGet } from '@/lib/api';
import type { PhotoItem } from '@/types/models';

export interface UploadOptions {
  signal?: AbortSignal;
  onUploadProgress?: (e: AxiosProgressEvent) => void;
}

/** Upload a single file (the endpoint takes a list; one-per-request gives us
 *  independent progress, cancel and retry per file). */
export async function uploadPhoto(eventId: number, file: File, opts?: UploadOptions): Promise<PhotoItem[]> {
  const form = new FormData();
  form.append('files', file);
  try {
    const res = await api.post<PhotoItem[]>(`/photos/upload/${eventId}`, form, {
      signal: opts?.signal,
      onUploadProgress: opts?.onUploadProgress,
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data;
  } catch (e) {
    throw toApiError(e);
  }
}

export function listEventPhotos(eventId: number): Promise<PhotoItem[]> {
  return httpGet<PhotoItem[]>(`/photos/event/${eventId}`);
}
