'use client';

import { useQuery } from '@tanstack/react-query';
import api from '@/lib/api';
import { Card, CardContent } from '@/components/ui/card';
import { Loader2 } from 'lucide-react';
import { PageHeader } from '@/components/layout/page-header';

interface Activity { id: number; action: string; event_id: number | null; ip_address: string | null; detail: Record<string, unknown> | null; created_at: string; }

export default function AdminAuditPage() {
  const { data, isLoading } = useQuery<Activity[]>({
    queryKey: ['admin-activity'], queryFn: async () => (await api.get('/admin/activity?limit=200')).data,
  });
  return (
    <div className="space-y-6">
      <PageHeader title="Audit Log" description="System activity across all events." />
      <Card>
        <CardContent className="pt-6 overflow-x-auto">
          {isLoading ? <Loader2 className="w-6 h-6 animate-spin" /> : (
            <table className="w-full text-sm">
              <thead><tr className="text-left text-muted-foreground border-b">
                <th className="py-2 pr-4 font-medium">Time</th><th className="py-2 px-2 font-medium">Action</th><th className="py-2 px-2 font-medium max-sm:hidden">Event</th>
                <th className="py-2 px-2 font-medium max-md:hidden">IP</th><th className="py-2 px-2 font-medium">Detail</th>
              </tr></thead>
              <tbody>
                {data?.map((a) => (
                  <tr key={a.id} className="border-b last:border-0 align-top">
                    <td className="py-2 pr-4 text-muted-foreground whitespace-nowrap">{new Date(a.created_at).toLocaleString()}</td>
                    <td className="py-2 px-2 font-mono text-xs">{a.action}</td>
                    <td className="py-2 px-2 max-sm:hidden">{a.event_id ?? '—'}</td>
                    <td className="py-2 px-2 font-mono text-xs max-md:hidden">{a.ip_address || '—'}</td>
                    <td className="py-2 px-2 text-xs text-muted-foreground">
                      {/* JSON blobs get long — wrap instead of forcing a huge horizontal scroll. */}
                      <span className="block max-w-[40ch] break-all lg:max-w-[60ch]">{a.detail ? JSON.stringify(a.detail) : '—'}</span>
                    </td>
                  </tr>
                ))}
                {!data?.length && <tr><td colSpan={5} className="py-4 text-muted-foreground">No activity yet.</td></tr>}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
