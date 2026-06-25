'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { MoreHorizontal, LayoutDashboard, Upload, QrCode, Link2, Eye, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';
import { guestUrl } from '@/lib/format';
import { useClickOutside } from '@/lib/hooks/use-click-outside';
import type { EventItem } from '@/types/models';

const ITEM = 'flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm hover:bg-accent';

export function EventActionMenu({
  event,
  onShowQr,
  onDelete,
}: {
  event: EventItem;
  onShowQr: (e: EventItem) => void;
  onDelete: (e: EventItem) => void;
}) {
  const [open, setOpen] = useState(false);
  const router = useRouter();
  const ref = useClickOutside<HTMLDivElement>(() => setOpen(false));

  const copyLink = async () => {
    await navigator.clipboard.writeText(guestUrl(event.event_slug));
    toast.success('Guest link copied');
    setOpen(false);
  };

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((v) => !v)}
        aria-label="Event actions"
        aria-haspopup="menu"
        aria-expanded={open}
        className="rounded-lg p-2 text-muted-foreground hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <MoreHorizontal className="h-4 w-4" />
      </button>
      {open && (
        <div role="menu" className="absolute right-0 z-50 mt-1 w-52 rounded-xl border bg-popover p-1 text-popover-foreground shadow-lg">
          <button role="menuitem" className={ITEM} onClick={() => { setOpen(false); router.push(`/events/${event.id}`); }}>
            <LayoutDashboard className="h-4 w-4" /> Open
          </button>
          <button role="menuitem" className={ITEM} onClick={() => { setOpen(false); router.push(`/events/${event.id}#upload`); }}>
            <Upload className="h-4 w-4" /> Upload photos
          </button>
          <button role="menuitem" className={ITEM} onClick={() => { setOpen(false); onShowQr(event); }}>
            <QrCode className="h-4 w-4" /> Generate QR
          </button>
          <button role="menuitem" className={ITEM} onClick={copyLink}>
            <Link2 className="h-4 w-4" /> Copy guest link
          </button>
          <a role="menuitem" className={ITEM} href={guestUrl(event.event_slug)} target="_blank" rel="noreferrer" onClick={() => setOpen(false)}>
            <Eye className="h-4 w-4" /> View gallery
          </a>
          <div className="my-1 h-px bg-border" />
          <button
            role="menuitem"
            className={cn(ITEM, 'text-red-600 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-500/10')}
            onClick={() => { setOpen(false); onDelete(event); }}
          >
            <Trash2 className="h-4 w-4" /> Delete
          </button>
        </div>
      )}
    </div>
  );
}
