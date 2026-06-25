import { describe, expect, it } from 'vitest';
import {
  getAnalytics,
  listUsers,
  getActivity,
  setUserRole,
  setUserLimit,
  setUserStorage,
  listTokens,
  createToken,
  revokeToken,
} from '@/services/admin';

describe('admin service (MSW-backed)', () => {
  it('reads analytics summary', async () => {
    const a = await getAnalytics();
    expect(a.total_events).toBe(3);
    expect(a.total_consents).toBe(18);
  });

  it('lists users with effective limits', async () => {
    const users = await listUsers();
    expect(users).toHaveLength(2);
    expect(users.find((u) => u.role === 'admin')).toBeTruthy();
  });

  it('passes the limit through to the activity query', async () => {
    const log = await getActivity(50);
    expect(log[0].action).toBe('EVENT_VIEWED');
  });

  it('promotes a user role', async () => {
    const u = await setUserRole(2, 'admin');
    expect(u.role).toBe('admin');
  });

  it('sets an event limit (and clears it with null)', async () => {
    expect((await setUserLimit(2, 5)).max_events).toBe(5);
    expect((await setUserLimit(2, null)).max_events).toBeNull();
  });

  it('sets a storage limit', async () => {
    const u = await setUserStorage(2, 4096);
    expect(u.storage_limit_mb).toBe(4096);
  });

  it('lists, creates, and revokes agent tokens', async () => {
    expect(await listTokens()).toHaveLength(1);
    const created = await createToken(2, 'ci-agent');
    expect(created.token).toBe('wfa_new_plaintext'); // plaintext returned once
    await expect(revokeToken(2)).resolves.toBeFalsy(); // 204
  });
});
