import { describe, expect, it } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import { renderWithProviders } from '../utils';
import EventsPage from '@/app/(dashboard)/events/page';

describe('Events page (integration)', () => {
  it('loads the studio events from the API', async () => {
    renderWithProviders(<EventsPage />);
    expect((await screen.findAllByText('Alpha Wedding')).length).toBeGreaterThan(0);
    expect(screen.getAllByText('Beta Wedding').length).toBeGreaterThan(0);
  });

  it('filters the list by search term', async () => {
    const { user } = renderWithProviders(<EventsPage />);
    await screen.findAllByText('Alpha Wedding');
    await user.type(screen.getByLabelText('Search'), 'alpha');
    await waitFor(() => expect(screen.queryAllByText('Beta Wedding')).toHaveLength(0));
    expect(screen.getAllByText('Alpha Wedding').length).toBeGreaterThan(0);
  });

  it('exposes a Create Event action', async () => {
    renderWithProviders(<EventsPage />);
    await screen.findAllByText('Alpha Wedding');
    expect(screen.getByRole('button', { name: /create event/i })).toBeInTheDocument();
  });
});
