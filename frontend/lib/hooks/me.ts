'use client';

import { useQuery } from '@tanstack/react-query';
import { useAuth } from '@/lib/auth-context';
import { getMe } from '@/services/auth';
import type { MeUser } from '@/types/models';

export type { MeUser };

/** Current backend user (role from Firestore RBAC, synced to Postgres).
 *  Enabled only once Firebase reports a signed-in user. */
export function useMe() {
  const { user } = useAuth();
  return useQuery<MeUser>({
    queryKey: ['me', user?.uid],
    enabled: !!user,
    queryFn: getMe,
  });
}
