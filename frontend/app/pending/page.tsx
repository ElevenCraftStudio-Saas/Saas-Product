'use client';

import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/lib/auth-context';
import { Clock } from 'lucide-react';

export default function PendingPage() {
  const router = useRouter();
  const { signOut } = useAuth();
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 p-6">
      <div className="max-w-md text-center space-y-4">
        <Clock className="mx-auto h-12 w-12 text-slate-400" />
        <h1 className="text-2xl font-bold">Access pending</h1>
        <p className="text-slate-500">
          Your account isn&apos;t active yet. Please contact your admin to be
          granted studio access.
        </p>
        <Button variant="outline" onClick={async () => { await signOut(); router.push('/login'); }}>
          Sign out
        </Button>
      </div>
    </div>
  );
}
