'use client';

import { useQuery } from '@tanstack/react-query';
import api from '@/lib/api';
import { useAuth } from '@/lib/auth-context';

export interface MeUser {
  id: number;
  role: 'admin' | 'user' | 'pending';
  email: string | null;
  name: string | null;
  max_events: number | null;
  storage_limit_mb: number | null;
}

export function useMe() {
  const { user } = useAuth();
  return useQuery<MeUser>({
    queryKey: ['me', user?.uid],
    enabled: !!user,
    queryFn: async () => (await api.get('/auth/me')).data,
  });
}
