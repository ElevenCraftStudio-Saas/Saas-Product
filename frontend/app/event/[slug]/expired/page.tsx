import { CalendarX } from 'lucide-react';

export default function GuestExpiredPage() {
  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-3 py-16 text-center">
      <CalendarX className="h-12 w-12 text-muted-foreground" aria-hidden />
      <h1 className="text-xl font-bold">This event has ended</h1>
      <p className="max-w-xs text-sm text-muted-foreground">
        Photo sharing for this event is no longer available. Please contact the wedding studio.
      </p>
    </main>
  );
}
