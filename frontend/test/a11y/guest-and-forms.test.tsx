import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ConsentCard } from '@/components/guest/consent-card';
import { EmptyGallery } from '@/components/guest/empty-gallery';

describe('ConsentCard accessibility + gating', () => {
  it('keeps Continue disabled until both consents are checked', async () => {
    const onAccept = vi.fn();
    render(<ConsentCard onAccept={onAccept} />);
    const cont = screen.getByRole('button', { name: /continue/i });
    expect(cont).toBeDisabled();

    const checks = screen.getAllByRole('checkbox');
    expect(checks).toHaveLength(2);
    await userEvent.click(checks[0]);
    expect(cont).toBeDisabled(); // only one accepted
    await userEvent.click(checks[1]);
    expect(cont).toBeEnabled();

    await userEvent.click(cont);
    expect(onAccept).toHaveBeenCalledOnce();
  });
});

describe('EmptyGallery', () => {
  it('offers a recovery action with an accessible name', async () => {
    const onRetake = vi.fn();
    render(<EmptyGallery onRetake={onRetake} />);
    expect(screen.getByText(/no photos found/i)).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /another selfie/i }));
    expect(onRetake).toHaveBeenCalledOnce();
  });
});
