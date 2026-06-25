import { describe, expect, it, vi, beforeEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';

// Control the upload service + silence toasts.
const uploadPhoto = vi.fn();
vi.mock('@/services/photos', () => ({ uploadPhoto: (...a: unknown[]) => uploadPhoto(...a) }));
vi.mock('sonner', () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

import { useUploadQueue } from '@/lib/hooks/use-upload-queue';

const jpg = (name = 'a.jpg', size = 100) => {
  const f = new File([new Uint8Array(size)], name, { type: 'image/jpeg' });
  return f;
};

beforeEach(() => uploadPhoto.mockReset());

describe('useUploadQueue', () => {
  it('uploads queued files to completion', async () => {
    uploadPhoto.mockResolvedValue([]);
    const onUploaded = vi.fn();
    const { result } = renderHook(() => useUploadQueue(1, { onUploaded }));
    act(() => result.current.add([jpg('a.jpg')]));
    await waitFor(() => expect(result.current.items[0]?.status).toBe('done'));
    expect(uploadPhoto).toHaveBeenCalledOnce();
    expect(onUploaded).toHaveBeenCalled();
    expect(result.current.aggregate.done).toBe(1);
  });

  it('skips duplicate files (name+size)', () => {
    uploadPhoto.mockResolvedValue([]);
    const { result } = renderHook(() => useUploadQueue(1));
    act(() => result.current.add([jpg('a.jpg', 50), jpg('a.jpg', 50)]));
    expect(result.current.items).toHaveLength(1);
  });

  it('rejects non-image / oversized files', () => {
    const { result } = renderHook(() => useUploadQueue(1));
    const txt = new File(['x'], 'notes.txt', { type: 'text/plain' });
    act(() => result.current.add([txt]));
    expect(result.current.items).toHaveLength(0);
  });

  it('marks failures and retries them', async () => {
    uploadPhoto.mockRejectedValueOnce(new Error('boom')).mockResolvedValueOnce([]);
    const { result } = renderHook(() => useUploadQueue(1));
    act(() => result.current.add([jpg('b.jpg')]));
    await waitFor(() => expect(result.current.items[0]?.status).toBe('error'));
    act(() => result.current.retryAllFailed());
    await waitFor(() => expect(result.current.items[0]?.status).toBe('done'));
  });

  it('removes an item from the queue', async () => {
    uploadPhoto.mockResolvedValue([]);
    const { result } = renderHook(() => useUploadQueue(1));
    act(() => result.current.add([jpg('c.jpg')]));
    await waitFor(() => expect(result.current.items[0]?.status).toBe('done'));
    const id = result.current.items[0].id;
    act(() => result.current.remove(id));
    expect(result.current.items).toHaveLength(0);
  });
});
