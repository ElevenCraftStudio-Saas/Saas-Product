'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Loader2, Copy } from 'lucide-react';
import { toast } from 'sonner';
import { PageHeader } from '@/components/layout/page-header';

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

export default function AdminUsersPage() {
  const qc = useQueryClient();
  const [newToken, setNewToken] = useState<{ user: string; token: string } | null>(null);

  const { data: users, isLoading } = useQuery<AdminUser[]>({
    queryKey: ['admin-users'],
    queryFn: async () => (await api.get('/admin/users')).data,
  });
  const onErr = (e: unknown) =>
    toast.error((e as { response?: { data?: { detail?: string } } }).response?.data?.detail || 'Failed');
  const invalidate = () => qc.invalidateQueries({ queryKey: ['admin-users'] });

  const setRole = useMutation({
    mutationFn: async ({ id, role }: { id: number; role: string }) =>
      (await api.patch(`/admin/users/${id}/role`, { role })).data,
    onSuccess: () => { toast.success('Role updated'); invalidate(); }, onError: onErr,
  });
  const setLimit = useMutation({
    mutationFn: async ({ id, max_events }: { id: number; max_events: number | null }) =>
      (await api.patch(`/admin/users/${id}/limit`, { max_events })).data,
    onSuccess: () => { toast.success('Event limit updated'); invalidate(); }, onError: onErr,
  });
  const setStorage = useMutation({
    mutationFn: async ({ id, storage_limit_mb }: { id: number; storage_limit_mb: number | null }) =>
      (await api.patch(`/admin/users/${id}/storage`, { storage_limit_mb })).data,
    onSuccess: () => { toast.success('Storage limit updated'); invalidate(); }, onError: onErr,
  });
  const createToken = useMutation({
    mutationFn: async ({ id }: { id: number; label: string }) =>
      (await api.post('/auth/tokens', { user_id: id, name: 'agent' })).data,
    onSuccess: (data, vars) => { setNewToken({ user: vars.label, token: data.token }); toast.success('Agent token created'); },
    onError: onErr,
  });

  if (isLoading) return <Loader2 className="w-6 h-6 animate-spin" />;

  return (
    <div className="space-y-6">
      <PageHeader title="Users" description="Roles, event and storage limits, agent tokens." />

      {newToken && (
        <Card>
          <CardContent className="pt-6 space-y-2">
            <p className="text-sm font-medium">Agent token for {newToken.user} — copy now, it won&apos;t be shown again:</p>
            <div className="flex flex-wrap items-center gap-2">
              <code className="min-w-0 flex-1 basis-full break-all rounded-md bg-muted px-3 py-2 text-xs sm:basis-auto">{newToken.token}</code>
              <Button size="sm" variant="outline" onClick={() => { navigator.clipboard.writeText(newToken.token); toast.success('Copied'); }}>
                <Copy className="w-4 h-4" />
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setNewToken(null)}>Dismiss</Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Desktop table */}
      <Card className="hidden lg:block">
        <CardContent className="pt-6 overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-muted-foreground border-b">
                <th className="py-2 pr-4 font-medium">User</th>
                <th className="py-2 px-2 font-medium">Role</th>
                <th className="py-2 px-2 font-medium">Events</th>
                <th className="py-2 px-2 font-medium">Event limit</th>
                <th className="py-2 px-2 font-medium">Storage</th>
                <th className="py-2 px-2 font-medium">Storage limit (MB)</th>
                <th className="py-2 px-2 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {users?.map((u) => (
                <tr key={u.id} className="border-b last:border-0 align-top">
                  <td className="py-2 pr-4">
                    <p className="font-medium">{u.name || u.email || `#${u.id}`}</p>
                    <p className="text-xs text-muted-foreground">{u.email}</p>
                  </td>
                  <td className="py-2 px-2"><RoleBadge role={u.role} /></td>
                  <td className="py-2 px-2 whitespace-nowrap">{u.event_count} / {u.effective_limit}</td>
                  <td className="py-2 px-2"><NumEditor value={u.max_events} onSave={(v) => setLimit.mutate({ id: u.id, max_events: v })} disabled={setLimit.isPending} /></td>
                  <td className="py-2 px-2 whitespace-nowrap">{u.storage_used_mb} / {u.effective_storage_limit_mb} MB</td>
                  <td className="py-2 px-2"><NumEditor value={u.storage_limit_mb} onSave={(v) => setStorage.mutate({ id: u.id, storage_limit_mb: v })} disabled={setStorage.isPending} /></td>
                  <td className="py-2 px-2">
                    <UserActions user={u} setRole={setRole} createToken={createToken} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>

      {/* Mobile / tablet cards */}
      <div className="space-y-3 lg:hidden">
        {users?.map((u) => (
          <Card key={u.id}>
            <CardContent className="pt-6 space-y-3">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="font-medium truncate">{u.name || u.email || `#${u.id}`}</p>
                  <p className="text-xs text-muted-foreground truncate">{u.email}</p>
                </div>
                <RoleBadge role={u.role} />
              </div>
              <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
                <dt className="text-muted-foreground">Events</dt>
                <dd className="text-right">{u.event_count} / {u.effective_limit}</dd>
                <dt className="text-muted-foreground">Storage</dt>
                <dd className="text-right">{u.storage_used_mb} / {u.effective_storage_limit_mb} MB</dd>
              </dl>
              <div className="space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs text-muted-foreground">Event limit</span>
                  <NumEditor value={u.max_events} onSave={(v) => setLimit.mutate({ id: u.id, max_events: v })} disabled={setLimit.isPending} />
                </div>
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs text-muted-foreground">Storage limit (MB)</span>
                  <NumEditor value={u.storage_limit_mb} onSave={(v) => setStorage.mutate({ id: u.id, storage_limit_mb: v })} disabled={setStorage.isPending} />
                </div>
              </div>
              <div className="flex flex-wrap gap-2 pt-1">
                <UserActions user={u} setRole={setRole} createToken={createToken} />
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}

function RoleBadge({ role }: { role: string }) {
  return (
    <span
      className={`shrink-0 text-xs px-2 py-0.5 rounded-full ${
        role === 'admin'
          ? 'bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-400'
          : 'bg-primary/10 text-primary'
      }`}
    >
      {role}
    </span>
  );
}

function UserActions({
  user: u,
  setRole,
  createToken,
}: {
  user: AdminUser;
  setRole: { mutate: (v: { id: number; role: string }) => void; isPending: boolean };
  createToken: { mutate: (v: { id: number; label: string }) => void; isPending: boolean };
}) {
  return (
    <div className="flex flex-col gap-1 lg:flex-col max-lg:flex-row max-lg:flex-wrap">
      {u.role === 'admin'
        ? <Button size="sm" variant="outline" onClick={() => setRole.mutate({ id: u.id, role: 'user' })} disabled={setRole.isPending}>Demote to User</Button>
        : <Button size="sm" onClick={() => setRole.mutate({ id: u.id, role: 'admin' })} disabled={setRole.isPending}>Promote to Admin</Button>}
      {u.role === 'user' && (
        <Button size="sm" variant="ghost" onClick={() => createToken.mutate({ id: u.id, label: u.email || `#${u.id}` })} disabled={createToken.isPending}>Create Agent Token</Button>
      )}
    </div>
  );
}

function NumEditor({ value, onSave, disabled }: { value: number | null; onSave: (v: number | null) => void; disabled: boolean }) {
  const [v, setV] = useState<string>(value === null ? '' : String(value));
  return (
    <div className="flex items-center gap-2">
      <input type="number" min={0} value={v} placeholder="default" onChange={(e) => setV(e.target.value)} className="h-8 w-24 rounded-md border border-input px-2 text-sm" />
      <Button size="sm" variant="outline" disabled={disabled} onClick={() => onSave(v.trim() === '' ? null : Math.max(0, parseInt(v, 10) || 0))}>Save</Button>
    </div>
  );
}
