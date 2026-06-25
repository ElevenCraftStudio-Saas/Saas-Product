'use client';

import { useRouter } from 'next/navigation';
import { LogOut } from 'lucide-react';
import { PageHeader } from '@/components/layout/page-header';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { useAuth } from '@/lib/auth-context';
import { useMe } from '@/lib/hooks/me';
import { formatStorage } from '@/lib/format';

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between border-b py-3 last:border-0">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-sm font-medium">{value}</span>
    </div>
  );
}

export default function ProfilePage() {
  const router = useRouter();
  const { signOut } = useAuth();
  const { data: me, isLoading } = useMe();

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <PageHeader title="Profile" description="Your account details." />
      <Card>
        <CardContent className="pt-6">
          {isLoading || !me ? (
            <div className="space-y-3">
              {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-6 w-full" />)}
            </div>
          ) : (
            <div>
              <Row label="Name" value={me.name || '—'} />
              <Row label="Email" value={me.email || '—'} />
              <Row label="Role" value={me.role} />
              <Row label="Event limit" value={me.max_events == null ? 'Default' : String(me.max_events)} />
              <Row label="Storage limit" value={me.storage_limit_mb == null ? 'Default' : formatStorage(me.storage_limit_mb)} />
            </div>
          )}
        </CardContent>
      </Card>
      <Button
        variant="outline"
        className="gap-2 text-red-600 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-500/10"
        onClick={async () => { await signOut(); router.replace('/login'); }}
      >
        <LogOut className="h-4 w-4" /> Sign out
      </Button>
    </div>
  );
}
