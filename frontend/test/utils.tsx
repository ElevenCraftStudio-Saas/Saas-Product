import { ReactElement } from 'react';
import { render, type RenderOptions } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import userEvent from '@testing-library/user-event';
import type { Mock } from 'vitest';

/** Fresh QueryClient per render: no retries, no cache bleed, no GC delay. */
export function makeTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0, staleTime: 0 },
      mutations: { retry: false },
    },
  });
}

export function renderWithProviders(ui: ReactElement, options?: RenderOptions) {
  const client = makeTestQueryClient();
  const Wrapper = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  return { user: userEvent.setup(), client, ...render(ui, { wrapper: Wrapper, ...options }) };
}

interface RouterMock { push: Mock; replace: Mock; back: Mock; prefetch: Mock; refresh: Mock; forward: Mock }
export function getRouter(): RouterMock {
  return (globalThis as unknown as { __router: RouterMock }).__router;
}
export function setParams(params: Record<string, string>) {
  (globalThis as unknown as { __navState: { params: Record<string, string> } }).__navState.params = params;
}
export function setPathname(pathname: string) {
  (globalThis as unknown as { __navState: { pathname: string } }).__navState.pathname = pathname;
}
