// Auth service — thin typed wrappers over the backend auth endpoints.
import { httpGet } from '@/lib/api';
import type { MeUser } from '@/types/models';

/** GET /auth/me — current user with backend role (Firestore-synced). */
export function getMe(): Promise<MeUser> {
  return httpGet<MeUser>('/auth/me');
}
