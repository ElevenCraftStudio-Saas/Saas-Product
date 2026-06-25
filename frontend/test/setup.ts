import '@testing-library/jest-dom/vitest';
import { afterAll, afterEach, beforeAll, vi } from 'vitest';
import { cleanup } from '@testing-library/react';
import { server } from './msw/server';

// --- Shared navigation mock (spies are reachable via test/utils getRouter) ---
const routerSpies = vi.hoisted(() => ({
  push: vi.fn(), replace: vi.fn(), back: vi.fn(), forward: vi.fn(), prefetch: vi.fn(), refresh: vi.fn(),
}));
const navState = vi.hoisted(() => ({ params: {} as Record<string, string>, pathname: '/' }));

vi.mock('next/navigation', () => ({
  useRouter: () => routerSpies,
  usePathname: () => navState.pathname,
  useParams: () => navState.params,
  useSearchParams: () => new URLSearchParams(),
  redirect: vi.fn(),
  notFound: vi.fn(),
}));

// --- Firebase mock (no real SDK init) ---
vi.mock('@/lib/firebase', () => ({
  auth: { currentUser: { uid: 'test-uid', getIdToken: vi.fn(async () => 'test-token') } },
  googleProvider: {},
  firebaseConfigured: true,
}));

// Expose to tests (typed accessors in ./utils).
(globalThis as unknown as { __router: typeof routerSpies }).__router = routerSpies;
(globalThis as unknown as { __navState: typeof navState }).__navState = navState;

// --- jsdom gaps ---
if (!URL.createObjectURL) URL.createObjectURL = vi.fn(() => 'blob:mock');
if (!URL.revokeObjectURL) URL.revokeObjectURL = vi.fn();
if (!window.matchMedia) {
  window.matchMedia = vi.fn().mockImplementation((q: string) => ({
    matches: false, media: q, onchange: null,
    addEventListener: vi.fn(), removeEventListener: vi.fn(),
    addListener: vi.fn(), removeListener: vi.fn(), dispatchEvent: vi.fn(),
  }));
}
if (!navigator.clipboard) {
  Object.defineProperty(navigator, 'clipboard', { value: { writeText: vi.fn(async () => undefined) }, configurable: true });
}

// --- MSW lifecycle ---
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => {
  server.resetHandlers();
  cleanup();
  routerSpies.push.mockClear();
  routerSpies.replace.mockClear();
  navState.params = {};
  navState.pathname = '/';
});
afterAll(() => server.close());
