'use client';

import Link from 'next/link';
import { ShieldX } from 'lucide-react';
import { Button } from '@/components/ui/button';

export default function UnauthorizedPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 p-8 text-center">
      <ShieldX className="h-12 w-12 text-destructive" />
      <h1 className="text-2xl font-bold">Access denied</h1>
      <p className="max-w-sm text-sm text-muted-foreground">
        You don’t have permission to view this page. If you think this is a mistake, contact your studio admin.
      </p>
      <Link href="/dashboard">
        <Button variant="outline" className="mt-2">Back to dashboard</Button>
      </Link>
    </div>
  );
}
