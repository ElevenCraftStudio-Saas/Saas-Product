// Event status is DERIVED on the client — the backend EventResponse has no
// status field. Centralized here so the badge + filters + KPIs agree.
export type EventStatus = 'upcoming' | 'active' | 'past';

const DAY_MS = 24 * 60 * 60 * 1000;

export function deriveStatus(eventDateIso: string, now: Date = new Date()): EventStatus {
  const t = new Date(eventDateIso).getTime();
  const n = now.getTime();
  if (t > n) return 'upcoming';
  if (n - t < DAY_MS) return 'active'; // within the event day
  return 'past';
}

export const STATUS_LABEL: Record<EventStatus, string> = {
  upcoming: 'Upcoming',
  active: 'Active',
  past: 'Past',
};
