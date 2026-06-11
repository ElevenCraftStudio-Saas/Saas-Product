'use client';

import { useQuery, useMutation } from '@tanstack/react-query';
import api from '@/lib/api';

export interface GuestEvent {
  id: number;
  title: string;
  description?: string | null;
  event_date: string;
  event_slug: string;
  url?: string | null;
}

export interface GuestPhoto {
  id: number;
  filename: string;
  url: string;
}

export interface SelfieMatchResult {
  count: number;
  photos: GuestPhoto[];
}

/** Backend serves local files relative to its host; S3 urls are absolute. */
export function absoluteUrl(url: string): string {
  if (!url) return url;
  if (url.startsWith('http://') || url.startsWith('https://')) return url;
  const base = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api').replace(/\/api\/?$/, '');
  return `${base}${url}`;
}

export function useGuestEvent(slug: string) {
  return useQuery<GuestEvent>({
    queryKey: ['guest-event', slug],
    queryFn: async () => (await api.get(`/guest/${slug}`)).data,
    enabled: Boolean(slug),
  });
}

export function useSelfieMatch(slug: string) {
  return useMutation<SelfieMatchResult, unknown, Blob>({
    mutationFn: async (blob: Blob) => {
      const fd = new FormData();
      fd.append('file', blob, 'selfie.jpg');
      fd.append('consent', 'true');
      const res = await api.post(`/guest/${slug}/selfie`, fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      return res.data;
    },
  });
}

export async function fetchDownloadUrl(slug: string, photoId: number): Promise<string> {
  const res = await api.get(`/guest/${slug}/photos/${photoId}/download`);
  return absoluteUrl(res.data.url);
}
