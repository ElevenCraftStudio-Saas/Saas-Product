import { describe, expect, it } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClientProvider } from '@tanstack/react-query';
import { makeTestQueryClient } from '../utils';
import { useStudioMetrics } from '@/lib/hooks/studio';
import { useDashboardMetrics } from '@/lib/hooks/admin';
import { useEventPhotos } from '@/lib/hooks/photos';

function wrapper({ children }: { children: React.ReactNode }) {
  return <QueryClientProvider client={makeTestQueryClient()}>{children}</QueryClientProvider>;
}

describe('useStudioMetrics', () => {
  it('counts events and derives active (non-past)', async () => {
    const { result } = renderHook(() => useStudioMetrics(), { wrapper });
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.metrics.events).toBe(2);
    expect(result.current.metrics.activeEvents).toBe(1); // 2030 future, 2020 past
    expect(result.current.metrics.photos).toBeNull(); // placeholder
  });
});

describe('useDashboardMetrics', () => {
  it('composes analytics + users storage', async () => {
    const { result } = renderHook(() => useDashboardMetrics(), { wrapper });
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.metrics?.events).toBe(3);
    expect(result.current.metrics?.guests).toBe(18);
    expect(result.current.metrics?.storageUsedMb).toBe(512); // summed across users
  });
});

describe('useEventPhotos', () => {
  it('loads photos with processing statuses', async () => {
    const { result } = renderHook(() => useEventPhotos(1), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toHaveLength(2);
    expect(result.current.data?.some((p) => p.processing_status === 'processing')).toBe(true);
  });
});
