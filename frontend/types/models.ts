// Shared domain types mirroring the FastAPI response schemas
// (backend/app/schemas/schemas.py). Keep in sync with the backend DTOs.

export type Role = 'admin' | 'user';

export type ProcessingStatus = 'pending' | 'processing' | 'completed' | 'failed';

/** GET /auth/me */
export interface MeUser {
  id: number;
  firebase_uid: string | null;
  name: string | null;
  email: string | null;
  phone: string | null;
  role: Role;
  max_events: number | null;
  storage_limit_mb: number | null;
  created_at: string;
}

/** Event (studio-owned) — POST/GET /events */
export interface EventItem {
  id: number;
  title: string;
  description: string | null;
  event_date: string;
  event_slug: string;
  qr_code_path: string | null;
  url: string | null; // presigned QR image url
  created_at: string;
  photographer_id: number;
}

export interface EventCreateInput {
  title: string;
  description?: string;
  event_date: string; // ISO
}

/** Photo — GET /photos/event/{id} */
export interface PhotoItem {
  id: number;
  event_id: number;
  filename: string;
  filepath: string;
  url: string | null; // presigned (thumbnail in lists, original on download)
  processing_status: ProcessingStatus;
  uploaded_at: string;
}

/** Admin user row — GET /admin/users */
export interface AdminUser {
  id: number;
  email: string | null;
  name: string | null;
  phone: string | null;
  role: Role;
  max_events: number | null;
  storage_limit_mb: number | null;
  event_count: number;
  effective_limit: number;
  effective_storage_limit_mb: number;
  storage_used_mb: number;
  created_at: string;
}

/** Audit log — GET /admin/activity */
export interface ActivityRecord {
  id: number;
  action: string;
  event_id: number | null;
  photo_id: number | null;
  ip_address: string | null;
  detail: Record<string, unknown> | null;
  created_at: string;
}

/** Analytics — GET /admin/analytics */
export interface EventAnalytics {
  event_id: number;
  title: string | null;
  photos: number;
  consents: number;
  scans: number;
  matches: number;
  downloads: number;
}
export interface AnalyticsSummary {
  total_events: number;
  total_photos: number;
  total_consents: number;
  total_scans: number;
  total_matches: number;
  total_downloads: number;
  per_event: EventAnalytics[];
}

/** API tokens — /auth/tokens (admin) */
export interface ApiTokenInfo {
  id: number;
  name: string | null;
  token_prefix: string | null;
  revoked: boolean;
  created_at: string;
  last_used_at: string | null;
}
export interface ApiTokenCreated extends ApiTokenInfo {
  token: string; // plaintext, shown once
}

/** Folder watch — /events/{id}/watch-folders (admin) */
export interface FolderWatch {
  id: number;
  event_id: number;
  folder_path: string;
  enabled: boolean;
  created_at: string;
  last_scan_at: string | null;
  watching: boolean;
  photo_count: number;
}

/** Guest flow — /guest/{slug}/* (public) */
export interface GuestEvent {
  id: number;
  title: string;
  description: string | null;
  event_date: string;
  event_slug: string;
  url: string | null;
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
