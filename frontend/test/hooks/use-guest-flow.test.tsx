import { describe, expect, it } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { QueryClientProvider } from '@tanstack/react-query';
import { makeTestQueryClient } from '../utils';
import { GuestFlowProvider, useGuestFlow } from '@/components/guest/guest-flow-provider';

function wrapper({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={makeTestQueryClient()}>
      <GuestFlowProvider slug="alpha-1">{children}</GuestFlowProvider>
    </QueryClientProvider>
  );
}

describe('useGuestFlow', () => {
  it('loads the public event and tracks consent/selfie/matches', async () => {
    const { result } = renderHook(() => useGuestFlow(), { wrapper });
    await waitFor(() => expect(result.current.event?.title).toBe('Alpha Wedding'));

    expect(result.current.consent).toBe(false);
    act(() => result.current.acceptConsent());
    expect(result.current.consent).toBe(true);

    const blob = new Blob(['x'], { type: 'image/jpeg' });
    act(() => result.current.setSelfie(blob));
    expect(result.current.selfie).toBe(blob);

    act(() => result.current.setMatches({ count: 1, photos: [{ id: 1, filename: 'a', url: 'u' }] }));
    expect(result.current.matches?.count).toBe(1);

    act(() => result.current.reset());
    expect(result.current.consent).toBe(false);
    expect(result.current.selfie).toBeNull();
    expect(result.current.matches).toBeNull();
  });
});
