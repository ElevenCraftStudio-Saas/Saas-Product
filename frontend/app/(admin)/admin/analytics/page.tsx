'use client';

import { useQuery } from '@tanstack/react-query';
import api from '@/lib/api';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { ShieldCheck, Eye, ScanFace, Download, Image as ImageIcon, Calendar, Loader2 } from 'lucide-react';
import { PageHeader } from '@/components/layout/page-header';

interface EventAnalytics { event_id: number; title: string | null; photos: number; consents: number; scans: number; matches: number; downloads: number; }
interface Analytics { total_events: number; total_photos: number; total_consents: number; total_scans: number; total_matches: number; total_downloads: number; per_event: EventAnalytics[]; }

function Stat({ icon, label, value }: { icon: React.ReactNode; label: string; value: number }) {
  return (
    <Card><CardContent className="pt-6"><div className="flex items-center gap-3">
      <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center text-primary">{icon}</div>
      <div><p className="text-2xl font-bold">{value}</p><p className="text-xs text-muted-foreground">{label}</p></div>
    </div></CardContent></Card>
  );
}

export default function AdminAnalyticsPage() {
  const { data, isLoading } = useQuery<Analytics>({
    queryKey: ['admin-analytics'], queryFn: async () => (await api.get('/admin/analytics')).data,
  });
  return (
    <div className="space-y-6">
      <PageHeader title="Analytics" description="Scans, matches and downloads per event." />
      {isLoading || !data ? <Loader2 className="w-6 h-6 animate-spin" /> : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
            <Stat icon={<Calendar />} label="Events" value={data.total_events} />
            <Stat icon={<ImageIcon className="w-5 h-5" />} label="Photos" value={data.total_photos} />
            <Stat icon={<ShieldCheck className="w-5 h-5" />} label="Consents" value={data.total_consents} />
            <Stat icon={<Eye className="w-5 h-5" />} label="Scans" value={data.total_scans} />
            <Stat icon={<ScanFace className="w-5 h-5" />} label="Matches" value={data.total_matches} />
            <Stat icon={<Download className="w-5 h-5" />} label="Downloads" value={data.total_downloads} />
          </div>
          <Card>
            <CardHeader><CardTitle className="text-lg">Per event</CardTitle></CardHeader>
            <CardContent className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead><tr className="text-left text-muted-foreground border-b">
                  <th className="py-2 pr-4">Event</th><th className="py-2 px-2">Photos</th><th className="py-2 px-2">Consents</th>
                  <th className="py-2 px-2">Scans</th><th className="py-2 px-2">Matches</th><th className="py-2 px-2">Downloads</th>
                </tr></thead>
                <tbody>
                  {data.per_event.map((e) => (
                    <tr key={e.event_id} className="border-b last:border-0">
                      <td className="py-2 pr-4 font-medium">{e.title || `#${e.event_id}`}</td>
                      <td className="py-2 px-2">{e.photos}</td><td className="py-2 px-2">{e.consents}</td>
                      <td className="py-2 px-2">{e.scans}</td><td className="py-2 px-2">{e.matches}</td><td className="py-2 px-2">{e.downloads}</td>
                    </tr>
                  ))}
                  {!data.per_event.length && <tr><td colSpan={6} className="py-4 text-muted-foreground">No events yet.</td></tr>}
                </tbody>
              </table>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
