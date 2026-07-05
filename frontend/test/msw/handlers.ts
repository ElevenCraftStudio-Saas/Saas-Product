import { http, HttpResponse } from 'msw';

const API = 'http://localhost:8000/api';

export const handlers = [
  http.get(`${API}/auth/me`, () =>
    HttpResponse.json({ id: 1, firebase_uid: 'u', name: 'Studio', email: 's@test.ai', phone: null, role: 'user', max_events: null, storage_limit_mb: null, created_at: '2026-01-01T00:00:00Z' }),
  ),

  http.get(`${API}/events/`, () =>
    HttpResponse.json([
      { id: 1, title: 'Alpha Wedding', description: null, event_date: '2030-01-01T00:00:00Z', event_slug: 'alpha-1', qr_code_path: 'qr/a', url: 'https://s3/qr/a.png', created_at: '2026-01-01T00:00:00Z', photographer_id: 1 },
      { id: 2, title: 'Beta Wedding', description: null, event_date: '2020-01-01T00:00:00Z', event_slug: 'beta-2', qr_code_path: 'qr/b', url: 'https://s3/qr/b.png', created_at: '2026-01-02T00:00:00Z', photographer_id: 1 },
    ]),
  ),

  http.get(`${API}/events/:id`, ({ params }) =>
    HttpResponse.json({ id: Number(params.id), title: 'Alpha Wedding', description: 'Venue', event_date: '2030-01-01T00:00:00Z', event_slug: 'alpha-1', qr_code_path: 'qr/a', url: 'https://s3/qr/a.png', created_at: '2026-01-01T00:00:00Z', photographer_id: 1 }),
  ),

  http.post(`${API}/events/`, async ({ request }) => {
    const body = (await request.json()) as { title: string };
    return HttpResponse.json({ id: 99, title: body.title, description: null, event_date: '2030-01-01T00:00:00Z', event_slug: 'new-99', qr_code_path: 'qr/n', url: 'https://s3/qr/n.png', created_at: '2026-01-03T00:00:00Z', photographer_id: 1 });
  }),

  http.delete(`${API}/events/:id`, () => new HttpResponse(null, { status: 204 })),

  http.get(`${API}/photos/event/:id`, () =>
    HttpResponse.json([
      { id: 10, event_id: 1, filename: 'a.jpg', filepath: 'k', url: 'https://s3/t/a.webp', processing_status: 'completed', uploaded_at: '2026-01-01T00:00:00Z' },
      { id: 11, event_id: 1, filename: 'b.jpg', filepath: 'k', url: 'https://s3/t/b.webp', processing_status: 'processing', uploaded_at: '2026-01-01T00:00:00Z' },
    ]),
  ),

  http.get(`${API}/admin/analytics`, () =>
    HttpResponse.json({ total_events: 3, total_photos: 120, total_consents: 18, total_scans: 40, total_matches: 30, total_downloads: 12, per_event: [
      { event_id: 1, title: 'Alpha', photos: 80, consents: 10, scans: 25, matches: 20, downloads: 8 },
    ] }),
  ),
  http.get(`${API}/admin/users`, () =>
    HttpResponse.json([
      { id: 1, email: 'a@test.ai', name: 'A', phone: null, role: 'admin', max_events: null, storage_limit_mb: null, event_count: 0, effective_limit: 2, effective_storage_limit_mb: 2048, storage_used_mb: 0, created_at: '2026-01-01T00:00:00Z' },
      { id: 2, email: 'u@test.ai', name: 'U', phone: null, role: 'user', max_events: null, storage_limit_mb: null, event_count: 3, effective_limit: 2, effective_storage_limit_mb: 2048, storage_used_mb: 512, created_at: '2026-01-01T00:00:00Z' },
    ]),
  ),
  http.patch(`${API}/admin/users/:id/role`, async ({ request, params }) => {
    const body = (await request.json()) as { role: string };
    return HttpResponse.json({ id: Number(params.id), email: 'u@test.ai', name: 'U', phone: null, role: body.role, max_events: null, storage_limit_mb: null, event_count: 0, effective_limit: 2, effective_storage_limit_mb: 2048, storage_used_mb: 0, created_at: '2026-01-01T00:00:00Z' });
  }),
  http.patch(`${API}/admin/users/:id/limit`, async ({ request, params }) => {
    const body = (await request.json()) as { max_events: number | null };
    return HttpResponse.json({ id: Number(params.id), email: 'u@test.ai', name: 'U', phone: null, role: 'user', max_events: body.max_events, storage_limit_mb: null, event_count: 0, effective_limit: body.max_events ?? 2, effective_storage_limit_mb: 2048, storage_used_mb: 0, created_at: '2026-01-01T00:00:00Z' });
  }),
  http.patch(`${API}/admin/users/:id/storage`, async ({ request, params }) => {
    const body = (await request.json()) as { storage_limit_mb: number | null };
    return HttpResponse.json({ id: Number(params.id), email: 'u@test.ai', name: 'U', phone: null, role: 'user', max_events: null, storage_limit_mb: body.storage_limit_mb, event_count: 0, effective_limit: 2, effective_storage_limit_mb: body.storage_limit_mb ?? 2048, storage_used_mb: 0, created_at: '2026-01-01T00:00:00Z' });
  }),
  http.get(`${API}/auth/tokens`, () =>
    HttpResponse.json([{ id: 1, name: 'agent', token_prefix: 'wfa_abc', revoked: false, created_at: '2026-01-01T00:00:00Z', last_used_at: null }]),
  ),
  http.post(`${API}/auth/tokens`, async ({ request }) => {
    const body = (await request.json()) as { user_id: number; name: string };
    return HttpResponse.json({ id: 2, name: body.name, token_prefix: 'wfa_new', revoked: false, created_at: '2026-01-01T00:00:00Z', last_used_at: null, token: 'wfa_new_plaintext' });
  }),
  http.delete(`${API}/auth/tokens/:id`, () => new HttpResponse(null, { status: 204 })),

  http.get(`${API}/admin/activity`, () =>
    HttpResponse.json([
      { id: 1, action: 'EVENT_VIEWED', event_id: 1, photo_id: null, ip_address: '1.1.1.1', detail: null, created_at: '2026-01-01T00:00:00Z' },
    ]),
  ),

  http.get(`${API}/guest/:slug`, ({ params }) =>
    HttpResponse.json({ id: 1, title: 'Alpha Wedding', description: 'Welcome', event_date: '2030-01-01T00:00:00Z', event_slug: String(params.slug), url: 'https://s3/qr/a.png' }),
  ),

  // Selfie POST returns immediately; matches arrive via the SSE stream.
  http.post(`${API}/guest/:slug/selfie`, () =>
    HttpResponse.json({ request_id: 'req-1', message: 'Processing started.' }),
  ),

  // Download requires a valid match token (anti-scraping).
  http.get(`${API}/guest/:slug/photos/:photoId/download`, ({ request }) => {
    const token = new URL(request.url).searchParams.get('token');
    if (!token) return HttpResponse.json({ detail: 'Invalid or expired download token.' }, { status: 403 });
    return HttpResponse.json({ url: 'https://s3/original/a.jpg', expires_in: 3600 });
  }),

  http.post(`${API}/guest/:slug/download-zip`, () =>
    HttpResponse.arrayBuffer(new ArrayBuffer(8), { headers: { 'Content-Type': 'application/zip' } }),
  ),
];
