import { describe, expect, it } from 'vitest';
import { http, HttpResponse } from 'msw';
import { server } from '../msw/server';
import { httpGet, SESSION_EXPIRED_EVENT } from '@/lib/api';
import { ApiError } from '@/lib/errors';

const API = 'http://localhost:8000/api';

describe('ApiError normalization', () => {
  it('extracts FastAPI detail strings', async () => {
    server.use(http.get(`${API}/boom`, () => HttpResponse.json({ detail: 'Event limit reached' }, { status: 403 })));
    await expect(httpGet('/boom')).rejects.toMatchObject({ status: 403, message: 'Event limit reached' });
  });

  it('flags network errors as status 0', async () => {
    server.use(http.get(`${API}/net`, () => HttpResponse.error()));
    const err = await httpGet('/net').catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(0);
    expect(err.code).toBe('network');
  });
});

describe('session expiration', () => {
  it('dispatches a session-expired event on a persistent 401', async () => {
    server.use(http.get(`${API}/secure`, () => HttpResponse.json({ detail: 'no' }, { status: 401 })));
    const fired = new Promise<void>((resolve) => {
      window.addEventListener(SESSION_EXPIRED_EVENT, () => resolve(), { once: true });
    });
    await httpGet('/secure').catch(() => undefined);
    await expect(Promise.race([fired, new Promise((_, r) => setTimeout(() => r(new Error('timeout')), 1000))])).resolves.toBeUndefined();
  });
});
