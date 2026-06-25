import { Camera } from 'lucide-react';

export function GuestHeader({ title }: { title?: string }) {
  return (
    <header className="flex items-center justify-center gap-2 py-4">
      <Camera className="h-5 w-5 text-primary" aria-hidden />
      <span className="truncate text-sm font-semibold">{title || 'WedFind AI'}</span>
    </header>
  );
}
