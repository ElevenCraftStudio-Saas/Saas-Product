import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ProcessingBadge } from '@/components/photos/processing-badge';
import { EventStatusBadge } from '@/components/events/event-status-badge';
import { deriveStatus } from '@/lib/event-status';

describe('ProcessingBadge', () => {
  it('maps each backend status to a label', () => {
    const { rerender } = render(<ProcessingBadge status="pending" />);
    expect(screen.getByText('Queued')).toBeInTheDocument();
    rerender(<ProcessingBadge status="processing" />);
    expect(screen.getByText('Processing')).toBeInTheDocument();
    rerender(<ProcessingBadge status="completed" />);
    expect(screen.getByText('Ready')).toBeInTheDocument();
    rerender(<ProcessingBadge status="failed" />);
    expect(screen.getByText('Failed')).toBeInTheDocument();
  });
});

describe('EventStatusBadge', () => {
  it('renders derived status labels', () => {
    const future = new Date(Date.now() + 5 * 86400000).toISOString();
    const past = new Date(Date.now() - 5 * 86400000).toISOString();
    render(<EventStatusBadge status={deriveStatus(future)} />);
    expect(screen.getByText('Upcoming')).toBeInTheDocument();
    render(<EventStatusBadge status={deriveStatus(past)} />);
    expect(screen.getByText('Past')).toBeInTheDocument();
  });
});
