import { describe, expect, it, vi, beforeEach } from 'vitest';
import { screen } from '@testing-library/react';
import { renderWithProviders, setPathname } from '../utils';
import { AppShell } from '@/components/layout/app-shell';
import { adminNav } from '@/components/layout/nav-config';

// UserMenu pulls signOut from the Firebase-backed auth context — stub it.
vi.mock('@/lib/auth-context', () => ({
  useAuth: () => ({ user: null, loading: false, signOut: vi.fn() }),
}));

describe('AppShell', () => {
  beforeEach(() => setPathname('/admin/users'));

  it('renders brand, nav, breadcrumbs, and the active item', async () => {
    renderWithProviders(
      <AppShell nav={adminNav} appName="WedFind Admin">
        <p>Page body</p>
      </AppShell>,
    );

    expect(screen.getByText('WedFind Admin')).toBeInTheDocument();
    expect(screen.getByText('Page body')).toBeInTheDocument();

    // Nav labels present.
    expect(screen.getByRole('link', { name: /users/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /agent tokens/i })).toBeInTheDocument();

    // Active item derives from the path.
    const usersLink = screen.getByRole('link', { name: /users/i });
    expect(usersLink).toHaveAttribute('aria-current', 'page');

    // Breadcrumb trail rendered from the path segments.
    expect(screen.getByRole('navigation', { name: /breadcrumb/i })).toBeInTheDocument();
  });
});
