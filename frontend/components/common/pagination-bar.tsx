'use client';

import { ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from '@/components/ui/button';

export function PaginationBar({
  page,
  pageCount,
  total,
  onPage,
}: {
  page: number;
  pageCount: number;
  total?: number;
  onPage: (page: number) => void;
}) {
  if (pageCount <= 1) return null;
  return (
    <div className="flex items-center justify-between gap-2 pt-3">
      <p className="text-sm text-muted-foreground">
        {total != null ? `${total} item${total === 1 ? '' : 's'} · ` : ''}Page {page} of {pageCount}
      </p>
      <div className="flex gap-1">
        <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => onPage(page - 1)} aria-label="Previous page">
          <ChevronLeft className="h-4 w-4" />
        </Button>
        <Button variant="outline" size="sm" disabled={page >= pageCount} onClick={() => onPage(page + 1)} aria-label="Next page">
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
