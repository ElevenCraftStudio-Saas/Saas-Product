// Events service — studio user endpoints (require role 'user').
import { httpGet, httpPost, httpDelete } from '@/lib/api';
import type { EventItem, EventCreateInput, PhotoItem } from '@/types/models';

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
