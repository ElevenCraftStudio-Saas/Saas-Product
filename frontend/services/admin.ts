// Admin service — management endpoints (require role 'admin').
import { httpGet, httpPatch, httpPost, httpDelete } from '@/lib/api';
import type {
  AdminUser,
  AnalyticsSummary,
  ActivityRecord,
  ApiTokenInfo,
  ApiTokenCreated,
  Role,
} from '@/types/models';

export function getAnalytics(): Promise<AnalyticsSummary> {
  return httpGet<AnalyticsSummary>('/admin/analytics');
}

export function listUsers(): Promise<AdminUser[]> {
  return httpGet<AdminUser[]>('/admin/users');
}

export function getActivity(limit = 100): Promise<ActivityRecord[]> {
  return httpGet<ActivityRecord[]>(`/admin/activity?limit=${limit}`);
}

export function setUserRole(id: number, role: Role): Promise<AdminUser> {
  return httpPatch<AdminUser>(`/admin/users/${id}/role`, { role });
}

export function setUserLimit(id: number, max_events: number | null): Promise<AdminUser> {
  return httpPatch<AdminUser>(`/admin/users/${id}/limit`, { max_events });
}

export function setUserStorage(id: number, storage_limit_mb: number | null): Promise<AdminUser> {
  return httpPatch<AdminUser>(`/admin/users/${id}/storage`, { storage_limit_mb });
}

export function listTokens(): Promise<ApiTokenInfo[]> {
  return httpGet<ApiTokenInfo[]>('/auth/tokens');
}

export function createToken(user_id: number, name: string): Promise<ApiTokenCreated> {
  return httpPost<ApiTokenCreated>('/auth/tokens', { user_id, name });
}

export function revokeToken(id: number): Promise<void> {
  return httpDelete<void>(`/auth/tokens/${id}`);
}
