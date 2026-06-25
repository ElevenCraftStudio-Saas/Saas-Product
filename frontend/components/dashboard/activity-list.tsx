'use client';

import { Eye, ScanFace, Download, ShieldCheck, Image as ImageIcon, Activity as ActivityIcon, type LucideIcon } from 'lucide-react';
import type { ActivityRecord } from '@/types/models';

const ICONS: Record<string, LucideIcon> = {
  EVENT_VIEWED: Eye,
  SELFIE_UPLOADED: ScanFace,
  FACE_MATCH_COMPLETED: ScanFace,
  PHOTO_DOWNLOADED: Download,
  CONSENT_RECORDED: ShieldCheck,
  PHOTO_UPLOADED: ImageIcon,
};

function label(action: string): string {
  return action.toLowerCase().replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return 'just now';
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

export function ActivityList({ items }: { items: ActivityRecord[] }) {
  return (
    <ul className="divide-y">
      {items.map((a) => {
        const Icon = ICONS[a.action] ?? ActivityIcon;
        return (
          <li key={a.id} className="flex items-center gap-3 py-3 first:pt-0 last:pb-0">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground">
              <Icon className="h-4 w-4" aria-hidden />
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium">{label(a.action)}</p>
              <p className="truncate text-xs text-muted-foreground">
                {a.event_id ? `Event #${a.event_id}` : 'System'}
                {a.ip_address ? ` · ${a.ip_address}` : ''}
              </p>
            </div>
            <time className="shrink-0 text-xs text-muted-foreground" dateTime={a.created_at}>
              {timeAgo(a.created_at)}
            </time>
          </li>
        );
      })}
    </ul>
  );
}
