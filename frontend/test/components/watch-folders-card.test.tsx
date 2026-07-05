import { describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { QueryClientProvider } from '@tanstack/react-query';
import { toast } from 'sonner';
import { makeTestQueryClient } from '../utils';
import { server } from '../msw/server';
import { WatchFoldersCard } from '@/components/events/watch-folders-card';

const API = 'http://localhost:8000/api';

function renderCard(eventId = 1) {
  return render(
    <QueryClientProvider client={makeTestQueryClient()}>
      <WatchFoldersCard eventId={eventId} />
    </QueryClientProvider>,
  );
}

describe('WatchFoldersCard', () => {
  it('lists watched folders with count and status', async () => {
    renderCard();
    expect(await screen.findByText(/Weddings\\Alpha/)).toBeInTheDocument();
    expect(screen.getByText(/12 photos/i)).toBeInTheDocument();
    expect(screen.getByText(/watching/i)).toBeInTheDocument();
  });

  it('adds a folder via the form', async () => {
    const success = vi.spyOn(toast, 'success');
    renderCard();
    await screen.findByText(/Weddings\\Alpha/);

    await userEvent.type(screen.getByPlaceholderText(/absolute folder path/i), 'E:\\More\\Photos');
    await userEvent.click(screen.getByRole('button', { name: /^add$/i }));

    await waitFor(() => expect(success).toHaveBeenCalled());
    success.mockRestore();
  });

  it('surfaces duplicate-folder 409 as an error toast', async () => {
    server.use(
      http.post(`${API}/events/:id/watch-folders`, () =>
        HttpResponse.json({ detail: 'This folder is already being watched for this event' }, { status: 409 }),
      ),
    );
    const error = vi.spyOn(toast, 'error');
    renderCard();
    await screen.findByText(/Weddings\\Alpha/);

    await userEvent.type(screen.getByPlaceholderText(/absolute folder path/i), 'D:\\Weddings\\Alpha');
    await userEvent.click(screen.getByRole('button', { name: /^add$/i }));

    await waitFor(() => expect(error).toHaveBeenCalled());
    error.mockRestore();
  });

  it('shows empty state when no folders watched', async () => {
    server.use(
      http.get(`${API}/events/:id/watch-folders`, () => HttpResponse.json([])),
    );
    renderCard();
    expect(await screen.findByText(/no folders watched/i)).toBeInTheDocument();
  });
});
