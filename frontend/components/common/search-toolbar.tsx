'use client';

import { Search } from 'lucide-react';
import { Input } from '@/components/ui/input';

/** Search field + slot for filter/sort controls. Reusable across list pages. */
export function SearchToolbar({
  value,
  onChange,
  placeholder = 'Search…',
  children,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="relative w-full sm:max-w-xs">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
        <Input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          aria-label="Search"
          className="pl-9"
        />
      </div>
      {children ? <div className="flex flex-wrap items-center gap-2">{children}</div> : null}
    </div>
  );
}
