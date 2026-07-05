// Events service — studio user endpoints (require role 'user').
import { httpGet, httpPost, httpDelete } from '@/lib/api';
import type { EventItem, EventCreateInput, PhotoItem, FolderWatch, RescanResult } from '@/types/models';

export function listEvents(): Promise<EventItem[]> {
  return httpGet<EventItem[]>('/events/');
}

export function getEvent(id: number): Promise<EventItem> {
  return httpGet<EventItem>(`/events/${id}`);
}

export function createEvent(input: EventCreateInput): Promise<EventItem> {
  return httpPost<EventItem>('/events/', {
    ...input,
    event_date: new Date(input.event_date).toISOString(),
  });
}

export function deleteEvent(id: number): Promise<void> {
  return httpDelete<void>(`/events/${id}`);
}

export function listEventPhotos(id: number): Promise<PhotoItem[]> {
  return httpGet<PhotoItem[]>(`/photos/event/${id}`);
}

// --- Folder watch (auto-import; owner-operable) ---

export function getWatchFolders(eventId: number): Promise<FolderWatch[]> {
  return httpGet<FolderWatch[]>(`/events/${eventId}/watch-folders`);
}

export function addWatchFolder(eventId: number, folderPath: string): Promise<FolderWatch> {
  return httpPost<FolderWatch>(`/events/${eventId}/watch-folders`, { folder_path: folderPath });
}

export function removeWatchFolder(eventId: number, watchId: number): Promise<void> {
  return httpDelete<void>(`/events/${eventId}/watch-folders/${watchId}`);
}

export function rescanFolder(eventId: number, watchId: number): Promise<RescanResult> {
  return httpPost<RescanResult>(`/events/${eventId}/watch-folders/${watchId}/rescan`);
}

export function rescanAllFolders(eventId: number): Promise<RescanResult> {
  return httpPost<RescanResult>(`/events/${eventId}/rescan-all`);
}
