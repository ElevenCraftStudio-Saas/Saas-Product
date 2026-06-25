import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QRCard } from '@/components/events/qr-card';
import { UploadQueueItem } from '@/components/photos/upload-queue-item';
import type { UploadItem } from '@/lib/hooks/use-upload-queue';

function item(overrides: Partial<UploadItem>): UploadItem {
  return { id: '1', file: new File(['x'], 'a.jpg'), name: 'a.jpg', size: 2048, status: 'queued', progress: 0, speedBps: 0, ...overrides };
}

describe('QRCard', () => {
  it('renders the guest url and copies it', async () => {
    render(<QRCard title="Alpha" slug="alpha-1" qrImageUrl="https://s3/qr.png" />);
    expect(screen.getByText(/\/event\/alpha-1$/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /copy/i }));
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(expect.stringContaining('/event/alpha-1'));
  });

  it('disables download when no QR image', () => {
    render(<QRCard title="Alpha" slug="alpha-1" qrImageUrl={null} />);
    expect(screen.getByRole('button', { name: /download/i })).toBeDisabled();
    expect(screen.getByText('QR unavailable')).toBeInTheDocument();
  });
});

describe('UploadQueueItem', () => {
  it('shows progress + speed while uploading', () => {
    render(<UploadQueueItem item={item({ status: 'uploading', progress: 40, speedBps: 1024 })} onRetry={() => {}} onCancel={() => {}} onRemove={() => {}} />);
    expect(screen.getByText(/40%/)).toBeInTheDocument();
  });

  it('shows error reason and retries', async () => {
    const onRetry = vi.fn();
    render(<UploadQueueItem item={item({ status: 'error', error: 'Boom' })} onRetry={onRetry} onCancel={() => {}} onRemove={() => {}} />);
    expect(screen.getByText('Boom')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /retry/i }));
    expect(onRetry).toHaveBeenCalledWith('1');
  });

  it('shows uploaded state and allows remove', async () => {
    const onRemove = vi.fn();
    render(<UploadQueueItem item={item({ status: 'done', progress: 100 })} onRetry={() => {}} onCancel={() => {}} onRemove={onRemove} />);
    expect(screen.getByText('Uploaded')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /remove/i }));
    expect(onRemove).toHaveBeenCalledWith('1');
  });
});
