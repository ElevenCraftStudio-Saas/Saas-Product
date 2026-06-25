import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MatchingTimeline } from '@/components/guest/matching-timeline';
import { GalleryGrid } from '@/components/guest/gallery-grid';
import { GuestHeader } from '@/components/guest/guest-header';
import { EventTable } from '@/components/events/event-table';
import { EventStatsGrid } from '@/components/events/event-stats-grid';
import { EventWorkspaceHeader } from '@/components/events/event-workspace-header';
import { ActivityList } from '@/components/dashboard/activity-list';
import { DashboardSection } from '@/components/dashboard/dashboard-section';
import { QuickActionCard } from '@/components/dashboard/quick-action-card';
import { UploadToolbar } from '@/components/photos/upload-toolbar';
import { UploadDropzone } from '@/components/photos/upload-dropzone';
import { Calendar } from 'lucide-react';
import type { EventItem, PhotoItem, GuestPhoto, ActivityRecord } from '@/types/models';

const event: EventItem = { id: 1, title: 'Alpha', description: null, event_date: '2030-01-01T00:00:00Z', event_slug: 'alpha-1', qr_code_path: null, url: null, created_at: '2026-01-01T00:00:00Z', photographer_id: 1 };
const photos: PhotoItem[] = [{ id: 1, event_id: 1, filename: 'a.jpg', filepath: 'k', url: 'u', processing_status: 'completed', uploaded_at: '2026-01-01T00:00:00Z' }];
const guestPhotos: GuestPhoto[] = [{ id: 1, filename: 'a.jpg', url: 'u' }, { id: 2, filename: 'b.jpg', url: 'u' }];
const activity: ActivityRecord[] = [{ id: 1, action: 'PHOTO_DOWNLOADED', event_id: 1, photo_id: null, ip_address: null, detail: null, created_at: new Date().toISOString() }];
const noop = () => {};

describe('render smoke (presentation components)', () => {
  it('MatchingTimeline shows stages', () => {
    render(<MatchingTimeline current={1} done={false} />);
    expect(screen.getByText('Detecting face')).toBeInTheDocument();
  });
  it('GalleryGrid renders all photos', () => {
    render(<GalleryGrid photos={guestPhotos} onOpen={noop} onDownload={noop} />);
    expect(screen.getAllByRole('img')).toHaveLength(2);
  });
  it('GuestHeader falls back to brand', () => {
    render(<GuestHeader />);
    expect(screen.getByText('WedFind AI')).toBeInTheDocument();
  });
  it('EventTable renders a row', () => {
    render(<EventTable events={[event]} onShowQr={noop} onDelete={noop} />);
    expect(screen.getByText('Alpha')).toBeInTheDocument();
  });
  it('EventStatsGrid derives counts', () => {
    render(<EventStatsGrid photos={photos} isLoading={false} />);
    expect(screen.getByText('Photos Uploaded')).toBeInTheDocument();
    expect(screen.getByText('Embeddings Ready')).toBeInTheDocument();
  });
  it('EventWorkspaceHeader shows title + disabled edit', () => {
    render(<EventWorkspaceHeader event={event} onShowQr={noop} onDelete={noop} />);
    expect(screen.getByText('Alpha')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /edit/i })).toBeDisabled();
  });
  it('ActivityList renders entries', () => {
    render(<ActivityList items={activity} />);
    expect(screen.getByText('Photo Downloaded')).toBeInTheDocument();
  });
  it('DashboardSection + QuickActionCard render', () => {
    render(
      <DashboardSection title="Recent" action={{ label: 'All', href: '/x' }}>
        <QuickActionCard label="Go" description="d" href="/x" icon={Calendar} />
      </DashboardSection>,
    );
    expect(screen.getByText('Recent')).toBeInTheDocument();
    expect(screen.getByText('Go')).toBeInTheDocument();
  });
  it('UploadToolbar shows progress summary', () => {
    render(<UploadToolbar aggregate={{ total: 3, done: 1, failed: 1, uploading: 1, queued: 0, overallProgress: 33, speedBps: 1024, etaSeconds: 10 }} onRetryFailed={noop} onClearCompleted={noop} onCancelAll={noop} />);
    expect(screen.getByText(/1\/3 uploaded/)).toBeInTheDocument();
    expect(screen.getByText(/1 failed/)).toBeInTheDocument();
  });
  it('UploadDropzone renders affordances', () => {
    render(<UploadDropzone onFiles={noop} />);
    expect(screen.getByText(/drag & drop/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /browse files/i })).toBeInTheDocument();
  });
});
