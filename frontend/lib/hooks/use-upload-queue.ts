'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { toast } from 'sonner';
import { uploadPhoto } from '@/services/photos';
import { toApiError } from '@/lib/errors';

export type UploadStatus = 'queued' | 'uploading' | 'done' | 'error' | 'canceled';

export interface UploadItem {
  id: string;
  file: File;
  name: string;
  size: number;
  status: UploadStatus;
  progress: number; // 0–100
  speedBps: number;
  error?: string;
  previewUrl?: string; // objectURL for image preview
}

const MAX_BYTES = 25 * 1024 * 1024; // matches backend MAX_FILE_SIZE
const ALLOWED = /\.(jpe?g|png|webp)$/i;
const CONCURRENCY = 3;

export interface UploadAggregate {
  total: number;
  done: number;
  failed: number;
  uploading: number;
  queued: number;
  overallProgress: number; // 0–100 across all bytes
  speedBps: number;
  etaSeconds: number;
}

export function useUploadQueue(eventId: number, opts?: { onUploaded?: () => void }) {
  const [items, setItems] = useState<UploadItem[]>([]);
  const itemsRef = useRef<UploadItem[]>([]);
  // Mirror the latest items into a ref for the event-driven callbacks (add /
  // fill) that read the queue without re-subscribing. Written in an effect
  // (not during render) so reads stay consistent with the committed state.
  useEffect(() => {
    itemsRef.current = items;
  }, [items]);
  const controllers = useRef<Map<string, AbortController>>(new Map());
  const activeRef = useRef(0);

  const patch = useCallback((id: string, p: Partial<UploadItem>) => {
    setItems((prev) => prev.map((it) => (it.id === id ? { ...it, ...p } : it)));
  }, []);

  const startOne = useCallback(
    async (item: UploadItem) => {
      activeRef.current += 1;
      patch(item.id, { status: 'uploading', progress: 0, error: undefined });
      const ctrl = new AbortController();
      controllers.current.set(item.id, ctrl);
      const startedAt = Date.now();
      try {
        await uploadPhoto(eventId, item.file, {
          signal: ctrl.signal,
          onUploadProgress: (e) => {
            const pct = e.total ? Math.round((e.loaded / e.total) * 100) : 0;
            const secs = (Date.now() - startedAt) / 1000;
            patch(item.id, { progress: pct, speedBps: secs > 0 ? e.loaded / secs : 0 });
          },
        });
        patch(item.id, { status: 'done', progress: 100, speedBps: 0 });
        opts?.onUploaded?.();
      } catch (err) {
        if (ctrl.signal.aborted) patch(item.id, { status: 'canceled', speedBps: 0 });
        else patch(item.id, { status: 'error', error: toApiError(err).message, speedBps: 0 });
      } finally {
        controllers.current.delete(item.id);
        activeRef.current -= 1;
        setItems((prev) => [...prev]); // nudge the effect to fill freed slots
      }
    },
    [eventId, opts, patch],
  );

  // Fill concurrency slots whenever the queue changes.
  useEffect(() => {
    if (activeRef.current >= CONCURRENCY) return;
    const queued = itemsRef.current.filter((i) => i.status === 'queued');
    for (const item of queued) {
      if (activeRef.current >= CONCURRENCY) break;
      void startOne(item);
    }
  }, [items, startOne]);

  const add = useCallback((files: File[]) => {
    const seen = new Set(itemsRef.current.map((i) => `${i.name}:${i.size}`));
    const next: UploadItem[] = [];
    let rejected = 0;
    for (const f of files) {
      if (!ALLOWED.test(f.name)) { rejected++; continue; }
      if (f.size > MAX_BYTES) { rejected++; continue; }
      const key = `${f.name}:${f.size}`;
      if (seen.has(key)) continue; // client-side duplicate skip
      seen.add(key);
      next.push({
        id: crypto.randomUUID(),
        file: f,
        name: f.name,
        size: f.size,
        status: 'queued',
        progress: 0,
        speedBps: 0,
        previewUrl: f.type.startsWith('image/') ? URL.createObjectURL(f) : undefined,
      });
    }
    if (rejected) toast.error(`${rejected} file(s) skipped (only JPG/PNG/WebP up to 25 MB).`);
    if (next.length) setItems((prev) => [...prev, ...next]);
  }, []);

  const retry = useCallback((id: string) => patch(id, { status: 'queued', progress: 0, error: undefined }), [patch]);
  const cancel = useCallback((id: string) => controllers.current.get(id)?.abort(), []);
  const remove = useCallback((id: string) => {
    setItems((prev) => {
      const target = prev.find((i) => i.id === id);
      if (target?.previewUrl) URL.revokeObjectURL(target.previewUrl);
      return prev.filter((i) => i.id !== id);
    });
  }, []);
  const clearCompleted = useCallback(() => {
    setItems((prev) => {
      prev.forEach((i) => { if (i.status === 'done' && i.previewUrl) URL.revokeObjectURL(i.previewUrl); });
      return prev.filter((i) => i.status !== 'done');
    });
  }, []);
  const retryAllFailed = useCallback(() => {
    setItems((prev) => prev.map((i) => (i.status === 'error' ? { ...i, status: 'queued', progress: 0, error: undefined } : i)));
  }, []);
  const cancelAll = useCallback(() => {
    controllers.current.forEach((c) => c.abort());
    setItems((prev) => prev.map((i) => (i.status === 'queued' ? { ...i, status: 'canceled' } : i)));
  }, []);

  // Revoke any remaining object URLs on unmount.
  useEffect(() => () => { itemsRef.current.forEach((i) => i.previewUrl && URL.revokeObjectURL(i.previewUrl)); }, []);

  const totalBytes = items.reduce((s, i) => s + i.size, 0);
  const loadedBytes = items.reduce((s, i) => s + (i.size * i.progress) / 100, 0);
  const speedBps = items.filter((i) => i.status === 'uploading').reduce((s, i) => s + i.speedBps, 0);
  const remainingBytes = totalBytes - loadedBytes;
  const aggregate: UploadAggregate = {
    total: items.length,
    done: items.filter((i) => i.status === 'done').length,
    failed: items.filter((i) => i.status === 'error').length,
    uploading: items.filter((i) => i.status === 'uploading').length,
    queued: items.filter((i) => i.status === 'queued').length,
    overallProgress: totalBytes ? Math.round((loadedBytes / totalBytes) * 100) : 0,
    speedBps,
    etaSeconds: speedBps > 0 ? remainingBytes / speedBps : Infinity,
  };

  return { items, aggregate, add, retry, cancel, remove, clearCompleted, retryAllFailed, cancelAll };
}
