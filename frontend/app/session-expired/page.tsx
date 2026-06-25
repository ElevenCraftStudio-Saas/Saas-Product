'use client';

import Link from 'next/link';
import { Clock } from 'lucide-react';
import { Button } from '@/components/ui/button';

export default function SessionExpiredPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 p-8 text-center">
      <Clock className="h-12 w-12 text-muted-foreground" />
      <h1 className="text-2xl font-bold">Session expired</h1>
      <p className="max-w-sm text-sm text-muted-foreground">
        For your security you’ve been signed out. Please sign in again to continue.
      </p>
      <Link href="/login">
        <Button className="mt-2">Sign in</Button>
      </Link>
    </div>
  );
}
