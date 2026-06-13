'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { ShieldCheck, FileDown, Loader2, Trash2 } from 'lucide-react';
import { toast } from 'sonner';

interface PrivacySummary {
  event_id: number;
  consent_count: number;
  photos_count: number;
  retention_days: number | null;
  scheduled_purge_at: string | null;
}

const RETENTION_OPTIONS = [
  { label: 'Keep forever', value: '' },
  { label: '30 days', value: '30' },
  { label: '90 days', value: '90' },
  { label: '180 days', value: '180' },
  { label: '1 year', value: '365' },
];

export function PrivacyPanel({ eventId }: { eventId: string | number }) {
  const qc = useQueryClient();

  const { data, isLoading } = useQuery<PrivacySummary>({
    queryKey: ['privacy', eventId],
    queryFn: async () => (await api.get(`/events/${eventId}/privacy`)).data,
  });

  const setRetention = useMutation({
    mutationFn: async (retention_days: number | null) =>
      (await api.patch(`/events/${eventId}/retention`, { retention_days })).data,
    onSuccess: () => {
      toast.success('Retention updated');
      qc.invalidateQueries({ queryKey: ['privacy', eventId] });
    },
    onError: () => toast.error('Failed to update retention'),
  });

  async function exportConsents(format: 'csv' | 'pdf') {
    try {
      const res = await api.get(`/events/${eventId}/consents/export?format=${format}`, {
        responseType: 'blob',
      });
      const url = URL.createObjectURL(res.data as Blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `consents-event-${eventId}.${format}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch {
      toast.error(`Could not export ${format.toUpperCase()}`);
    }
  }

  return (
    <Card className="lg:col-span-3">
      <CardHeader>
        <CardTitle className="flex items-center space-x-2">
          <ShieldCheck className="w-5 h-5 text-primary" />
          <span>Privacy &amp; Compliance (DPDP)</span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        {isLoading || !data ? (
          <Loader2 className="w-5 h-5 animate-spin" />
        ) : (
          <>
            <div className="flex flex-wrap gap-6 text-sm">
              <span className="text-slate-500">
                Consent records: <b className="text-slate-900">{data.consent_count}</b>
              </span>
              <span className="text-slate-500">
                Photos: <b className="text-slate-900">{data.photos_count}</b>
              </span>
              <span className="text-slate-500">
                Scheduled deletion:{' '}
                <b className="text-slate-900">
                  {data.scheduled_purge_at
                    ? new Date(data.scheduled_purge_at).toLocaleDateString()
                    : 'Never'}
                </b>
              </span>
            </div>

            {/* Retention control */}
            <div className="space-y-2">
              <label className="text-sm font-medium flex items-center gap-2">
                <Trash2 className="w-4 h-4 text-slate-400" />
                Auto-delete photos &amp; face data after
              </label>
              <select
                className="border rounded-md px-3 py-2 text-sm w-56"
                value={data.retention_days ?? ''}
                onChange={(e) =>
                  setRetention.mutate(e.target.value === '' ? null : Number(e.target.value))
                }
                disabled={setRetention.isPending}
              >
                {RETENTION_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
              <p className="text-xs text-slate-400">
                Counted from the event date. Faces and photos are permanently purged — consent
                records are kept as legal proof.
              </p>
            </div>

            {/* Consent export */}
            <div className="space-y-2 border-t pt-4">
              <p className="text-sm font-medium">Proof-of-consent ledger</p>
              <div className="flex gap-2">
                <Button size="sm" variant="outline" onClick={() => exportConsents('csv')}>
                  <FileDown className="w-4 h-4 mr-1" /> Export CSV
                </Button>
                <Button size="sm" variant="outline" onClick={() => exportConsents('pdf')}>
                  <FileDown className="w-4 h-4 mr-1" /> Export PDF
                </Button>
              </div>
              <p className="text-xs text-slate-400">
                Audit-ready record of every guest&apos;s biometric consent (timestamp, IP, version, text).
              </p>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
