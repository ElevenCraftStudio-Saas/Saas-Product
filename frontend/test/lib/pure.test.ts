import { describe, expect, it } from 'vitest';
import { formatBytes, formatSpeed, formatDuration, formatStorage, formatDate, guestUrl } from '@/lib/format';
import { deriveStatus } from '@/lib/event-status';
import { ApiError } from '@/lib/errors';

describe('format helpers', () => {
  it('formats bytes across units', () => {
    expect(formatBytes(512)).toBe('512 B');
    expect(formatBytes(2048)).toBe('2.0 KB');
    expect(formatBytes(5 * 1024 * 1024)).toBe('5.0 MB');
    expect(formatBytes(3 * 1024 * 1024 * 1024)).toBe('3.00 GB');
  });
  it('formats speed and guards zero', () => {
    expect(formatSpeed(0)).toBe('—');
    expect(formatSpeed(1024)).toBe('1.0 KB/s');
  });
  it('formats duration and guards infinity', () => {
    expect(formatDuration(Infinity)).toBe('—');
    expect(formatDuration(45)).toBe('45s');
    expect(formatDuration(90)).toBe('1m 30s');
  });
  it('formats storage MB→GB', () => {
    expect(formatStorage(500)).toBe('500 MB');
    expect(formatStorage(2048)).toBe('2.0 GB');
  });
  it('builds a guest url and formats a date', () => {
    expect(guestUrl('abc')).toMatch(/\/event\/abc$/);
    expect(formatDate('2030-01-15T00:00:00Z')).toMatch(/2030/);
  });
});

describe('deriveStatus', () => {
  const now = new Date('2026-06-25T12:00:00Z');
  it('classifies future / today / past', () => {
    expect(deriveStatus('2026-12-01T00:00:00Z', now)).toBe('upcoming');
    expect(deriveStatus('2026-06-25T06:00:00Z', now)).toBe('active'); // same day
    expect(deriveStatus('2020-01-01T00:00:00Z', now)).toBe('past');
  });
});

describe('ApiError', () => {
  it('exposes status helpers', () => {
    expect(new ApiError('x', 401).isAuth).toBe(true);
    expect(new ApiError('x', 403).isForbidden).toBe(true);
    expect(new ApiError('x', 404).isNotFound).toBe(true);
    expect(new ApiError('x', 500).code).toBe('x');
  });
});
