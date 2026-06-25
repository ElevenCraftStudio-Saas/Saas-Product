import { SearchX } from 'lucide-react';

export default function GuestEventNotFoundPage() {
  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-3 py-16 text-center">
      <SearchX className="h-12 w-12 text-muted-foreground" aria-hidden />
      <h1 className="text-xl font-bold">Event not found</h1>
      <p className="max-w-xs text-sm text-muted-foreground">
        Double-check the QR code or link from your invitation.
      </p>
    </main>
  );
}
