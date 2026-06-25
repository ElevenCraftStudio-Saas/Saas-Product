import { describe, expect, it, vi } from 'vitest';
import { http, HttpResponse } from 'msw';
import { server } from '../msw/server';
import api from '@/lib/api';
import { listEvents, createEvent, deleteEvent } from '@/services/events';
import { getGuestEvent, submitSelfie, getDownloadUrl } from '@/services/guest';

const API = 'http://localhost:8000/api';

describe('events service', () => {
  it('lists events', async () => {
    const events = await listEvents();
    expect(events).toHaveLength(2);
    expect(events[0].event_slug).toBe('alpha-1');
  });

  it('creates an event with an ISO date', async () => {
    let sentBody: { event_date?: string } = {};
    server.use(http.post(`${API}/events/`, async ({ request }) => {
      sentBody = (await request.json()) as { event_date?: string };
      return HttpResponse.json({ id: 99, title: 'X', description: null, event_date: sentBody.event_date, event_slug: 'x-99', qr_code_path: null, url: null, created_at: '2026-01-01T00:00:00Z', photographer_id: 1 });
    }));
    const created = await createEvent({ title: 'X', event_date: '2030-05-01' });
    expect(created.id).toBe(99);
    expect(sentBody.event_date).toMatch(/T/); // normalized to ISO
  });

  it('deletes an event (204 → resolves without error)', async () => {
    await expect(deleteEvent(1)).resolves.toBeFalsy(); // 204 has an empty body
  });
});

describe('guest service', () => {
  it('fetches the public event', async () => {
    const ev = await getGuestEvent('alpha-1');
    expect(ev.title).toBe('Alpha Wedding');
  });

  it('submits a selfie as multipart (file + consent) and maps the result', async () => {
    // axios multipart over jsdom+MSW hangs, so spy the call instead of the wire.
    const spy = vi.spyOn(api, 'post').mockResolvedValue({ data: { count: 2, photos: [{ id: 10, filename: 'a.jpg', url: 'u' }] } });
    const res = await submitSelfie('alpha-1', new Blob(['x'], { type: 'image/jpeg' }));
    expect(spy).toHaveBeenCalledWith('/guest/alpha-1/selfie', expect.any(FormData), expect.objectContaining({ headers: { 'Content-Type': 'multipart/form-data' } }));
    const sentForm = spy.mock.calls[0][1] as FormData;
    expect(sentForm.get('consent')).toBe('true');
    expect(sentForm.has('file')).toBe(true);
    expect(res.count).toBe(2);
    spy.mockRestore();
  });

  it('resolves a presigned download url', async () => {
    const url = await getDownloadUrl('alpha-1', 10);
    expect(url).toBe('https://s3/original/a.jpg');
  });
});
