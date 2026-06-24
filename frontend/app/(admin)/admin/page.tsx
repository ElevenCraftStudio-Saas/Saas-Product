'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import {
  ShieldCheck, BarChart3, Users, ScrollText, Loader2,
  Eye, ScanFace, Download, Image as ImageIcon, Calendar,
} from 'lucide-react';
import { toast } from 'sonner';

type Tab = 'analytics' | 'users' | 'activity';

interface EventAnalytics {
  event_id: number;
  title: string | null;
  photos: number;
  consents: number;
  scans: number;
  matches: number;
  downloads: number;
}
interface Analytics {
  total_events: number;
  total_photos: number;
  total_consents: number;
  total_scans: number;
  total_matches: number;
  total_downloads: number;
  per_event: EventAnalytics[];
}
interface AdminUser {
  id: number;
  email: string | null;
  name: string | null;
  phone: string | null;
  role: string;
  max_events: number | null;
  storage_limit_mb: number | null;
  event_count: number;
  effective_limit: number;
  effective_storage_limit_mb: number;
  storage_used_mb: number;
  created_at: string;
}
interface Activity {
  id: number;
  action: string;
  event_id: number | null;
  ip_address: string | null;
  detail: Record<string, unknown> | null;
  created_at: string;
}

export default function AdminPage() {
  const [tab, setTab] = useState<Tab>('users');

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold flex items-center gap-2">
        <ShieldCheck className="w-7 h-7 text-primary" /> Admin
      </h1>

      <div className="flex gap-2 border-b">
        <TabBtn active={tab === 'users'} onClick={() => setTab('users')} icon={<Users className="w-4 h-4" />} label="Users" />
        <TabBtn active={tab === 'analytics'} onClick={() => setTab('analytics')} icon={<BarChart3 className="w-4 h-4" />} label="Analytics" />
        <TabBtn active={tab === 'activity'} onClick={() => setTab('activity')} icon={<ScrollText className="w-4 h-4" />} label="Audit Log" />
      </div>

      {tab === 'analytics' && <AnalyticsTab />}
      {tab === 'users' && <UsersTab />}
      {tab === 'activity' && <ActivityTab />}
    </div>
  );
}

function TabBtn({ active, onClick, icon, label }: { active: boolean; onClick: () => void; icon: React.ReactNode; label: string }) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
        active ? 'border-primary text-primary' : 'border-transparent text-slate-500 hover:text-slate-800'
      }`}
    >
      {icon} {label}
    </button>
  );
}

function Stat({ icon, label, value }: { icon: React.ReactNode; label: string; value: number }) {
  return (
    <Card>
      <CardContent className="pt-6">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center text-primary">{icon}</div>
          <div>
            <p className="text-2xl font-bold">{value}</p>
            <p className="text-xs text-slate-500">{label}</p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function AnalyticsTab() {
  const { data, isLoading } = useQuery<Analytics>({
    queryKey: ['admin-analytics'],
    queryFn: async () => (await api.get('/admin/analytics')).data,
  });
  if (isLoading || !data) return <Loader2 className="w-6 h-6 animate-spin" />;
  return (
    <div className="space-y-6">
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
            <thead>
              <tr className="text-left text-slate-500 border-b">
                <th className="py-2 pr-4">Event</th>
                <th className="py-2 px-2">Photos</th>
                <th className="py-2 px-2">Consents</th>
                <th className="py-2 px-2">Scans</th>
                <th className="py-2 px-2">Matches</th>
                <th className="py-2 px-2">Downloads</th>
              </tr>
            </thead>
            <tbody>
              {data.per_event.map((e) => (
                <tr key={e.event_id} className="border-b last:border-0">
                  <td className="py-2 pr-4 font-medium">{e.title || `#${e.event_id}`}</td>
                  <td className="py-2 px-2">{e.photos}</td>
                  <td className="py-2 px-2">{e.consents}</td>
                  <td className="py-2 px-2">{e.scans}</td>
                  <td className="py-2 px-2">{e.matches}</td>
                  <td className="py-2 px-2">{e.downloads}</td>
                </tr>
              ))}
              {!data.per_event.length && (
                <tr><td colSpan={6} className="py-4 text-slate-400">No events yet.</td></tr>
              )}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  );
}

function UsersTab() {
  const qc = useQueryClient();
  const { data: users, isLoading } = useQuery<AdminUser[]>({
    queryKey: ['admin-users'],
    queryFn: async () => (await api.get('/admin/users')).data,
  });
  const onErr = (e: unknown) =>
    toast.error((e as { response?: { data?: { detail?: string } } }).response?.data?.detail || 'Failed');
  const setRole = useMutation({
    mutationFn: async ({ id, role }: { id: number; role: string }) =>
      (await api.patch(`/admin/users/${id}/role`, { role })).data,
    onSuccess: () => { toast.success('Role updated'); qc.invalidateQueries({ queryKey: ['admin-users'] }); },
    onError: onErr,
  });
  const setLimit = useMutation({
    mutationFn: async ({ id, max_events }: { id: number; max_events: number | null }) =>
      (await api.patch(`/admin/users/${id}/limit`, { max_events })).data,
    onSuccess: () => { toast.success('Event limit updated'); qc.invalidateQueries({ queryKey: ['admin-users'] }); },
    onError: onErr,
  });
  const setStorage = useMutation({
    mutationFn: async ({ id, storage_limit_mb }: { id: number; storage_limit_mb: number | null }) =>
      (await api.patch(`/admin/users/${id}/storage`, { storage_limit_mb })).data,
    onSuccess: () => { toast.success('Storage limit updated'); qc.invalidateQueries({ queryKey: ['admin-users'] }); },
    onError: onErr,
  });

  if (isLoading) return <Loader2 className="w-6 h-6 animate-spin" />;
  return (
    <Card>
      <CardContent className="pt-6 overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-slate-500 border-b">
              <th className="py-2 pr-4">User</th>
              <th className="py-2 px-2">Role</th>
              <th className="py-2 px-2">Events</th>
              <th className="py-2 px-2">Event limit</th>
              <th className="py-2 px-2">Storage</th>
              <th className="py-2 px-2">Storage limit (MB)</th>
              <th className="py-2 px-2">Action</th>
            </tr>
          </thead>
          <tbody>
            {users?.map((u) => (
              <tr key={u.id} className="border-b last:border-0">
                <td className="py-2 pr-4">
                  <p className="font-medium">{u.name || u.email || `#${u.id}`}</p>
                  <p className="text-xs text-slate-400">{u.email}</p>
                </td>
                <td className="py-2 px-2">
                  <span className={`text-xs px-2 py-0.5 rounded-full ${
                    u.role === 'admin' ? 'bg-amber-100 text-amber-700'
                    : u.role === 'user' ? 'bg-primary/10 text-primary'
                    : 'bg-slate-100 text-slate-600'}`}>{u.role}</span>
                </td>
                <td className="py-2 px-2 whitespace-nowrap">{u.event_count} / {u.effective_limit}</td>
                <td className="py-2 px-2">
                  {u.role === 'admin' ? '—'
                   : <NumEditor value={u.max_events} onSave={(v) => setLimit.mutate({ id: u.id, max_events: v })} disabled={setLimit.isPending} />}
                </td>
                <td className="py-2 px-2 whitespace-nowrap">{u.storage_used_mb} / {u.effective_storage_limit_mb} MB</td>
                <td className="py-2 px-2">
                  {u.role === 'admin' ? '—'
                   : <NumEditor value={u.storage_limit_mb} onSave={(v) => setStorage.mutate({ id: u.id, storage_limit_mb: v })} disabled={setStorage.isPending} />}
                </td>
                <td className="py-2 px-2">
                  {u.role === 'admin' ? '—'
                   : u.role === 'user'
                    ? <Button size="sm" variant="outline" onClick={() => setRole.mutate({ id: u.id, role: 'pending' })} disabled={setRole.isPending}>Revoke</Button>
                    : <Button size="sm" onClick={() => setRole.mutate({ id: u.id, role: 'user' })} disabled={setRole.isPending}>Grant user</Button>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}

function NumEditor({ value, onSave, disabled }: { value: number | null; onSave: (v: number | null) => void; disabled: boolean }) {
  const [v, setV] = useState<string>(value === null ? '' : String(value));
  return (
    <div className="flex items-center gap-2">
      <input
        type="number" min={0} value={v} placeholder="default"
        onChange={(e) => setV(e.target.value)}
        className="h-8 w-24 rounded-md border border-input px-2 text-sm"
      />
      <Button size="sm" variant="outline" disabled={disabled}
        onClick={() => onSave(v.trim() === '' ? null : Math.max(0, parseInt(v, 10) || 0))}>
        Save
      </Button>
    </div>
  );
}

function ActivityTab() {
  const { data, isLoading } = useQuery<Activity[]>({
    queryKey: ['admin-activity'],
    queryFn: async () => (await api.get('/admin/activity?limit=200')).data,
  });
  if (isLoading) return <Loader2 className="w-6 h-6 animate-spin" />;
  return (
    <Card>
      <CardContent className="pt-6 overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-slate-500 border-b">
              <th className="py-2 pr-4">Time</th>
              <th className="py-2 px-2">Action</th>
              <th className="py-2 px-2">Event</th>
              <th className="py-2 px-2">IP</th>
              <th className="py-2 px-2">Detail</th>
            </tr>
          </thead>
          <tbody>
            {data?.map((a) => (
              <tr key={a.id} className="border-b last:border-0">
                <td className="py-2 pr-4 text-slate-400 whitespace-nowrap">{new Date(a.created_at).toLocaleString()}</td>
                <td className="py-2 px-2 font-mono text-xs">{a.action}</td>
                <td className="py-2 px-2">{a.event_id ?? '—'}</td>
                <td className="py-2 px-2 font-mono text-xs">{a.ip_address || '—'}</td>
                <td className="py-2 px-2 text-xs text-slate-500">{a.detail ? JSON.stringify(a.detail) : '—'}</td>
              </tr>
            ))}
            {!data?.length && (
              <tr><td colSpan={5} className="py-4 text-slate-400">No activity yet.</td></tr>
            )}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}
