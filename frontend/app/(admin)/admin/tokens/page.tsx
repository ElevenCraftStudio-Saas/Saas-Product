'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Loader2, Copy } from 'lucide-react';
import { toast } from 'sonner';
import { PageHeader } from '@/components/layout/page-header';

interface AdminUser { id: number; email: string | null; name: string | null; role: string; }
interface TokenInfo { id: number; name: string | null; token_prefix: string | null; revoked: boolean; created_at: string; last_used_at: string | null; }

export default function AdminTokensPage() {
  const qc = useQueryClient();
  const [userId, setUserId] = useState<string>('');
  const [name, setName] = useState<string>('agent');
  const [created, setCreated] = useState<string | null>(null);

  const { data: users } = useQuery<AdminUser[]>({
    queryKey: ['admin-users'], queryFn: async () => (await api.get('/admin/users')).data,
  });
  const { data: tokens, isLoading } = useQuery<TokenInfo[]>({
    queryKey: ['admin-tokens'], queryFn: async () => (await api.get('/auth/tokens')).data,
  });
  const onErr = (e: unknown) =>
    toast.error((e as { response?: { data?: { detail?: string } } }).response?.data?.detail || 'Failed');

  const create = useMutation({
    mutationFn: async () => (await api.post('/auth/tokens', { user_id: Number(userId), name })).data,
    onSuccess: (d) => { setCreated(d.token); toast.success('Token created'); qc.invalidateQueries({ queryKey: ['admin-tokens'] }); },
    onError: onErr,
  });
  const revoke = useMutation({
    mutationFn: async (id: number) => (await api.delete(`/auth/tokens/${id}`)).data,
    onSuccess: () => { toast.success('Revoked'); qc.invalidateQueries({ queryKey: ['admin-tokens'] }); },
    onError: onErr,
  });

  const userOptions = (users || []).filter((u) => u.role === 'user');

  return (
    <div className="space-y-6">
      <PageHeader title="Agent Tokens" description="Create and revoke desktop-agent keys, assigned per user." />

      <Card>
        <CardHeader><CardTitle className="text-lg">Create agent token</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <select value={userId} onChange={(e) => setUserId(e.target.value)} className="h-9 rounded-md border border-input px-2 text-sm">
              <option value="">Select user…</option>
              {userOptions.map((u) => <option key={u.id} value={u.id}>{u.email || u.name || `#${u.id}`}</option>)}
            </select>
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="label" className="h-9 w-40 rounded-md border border-input px-2 text-sm" />
            <Button disabled={!userId || create.isPending} onClick={() => create.mutate()}>Create</Button>
          </div>
          {created && (
            <div className="flex flex-wrap items-center gap-2">
              <code className="min-w-0 flex-1 basis-full break-all rounded-md bg-muted px-3 py-2 text-xs sm:basis-auto">{created}</code>
              <Button size="sm" variant="outline" onClick={() => { navigator.clipboard.writeText(created); toast.success('Copied'); }}><Copy className="w-4 h-4" /></Button>
              <Button size="sm" variant="ghost" onClick={() => setCreated(null)}>Dismiss</Button>
            </div>
          )}
          <p className="text-xs text-muted-foreground">Tokens may only be assigned to studio <b>user</b> accounts. The plaintext is shown once.</p>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="pt-6 overflow-x-auto">
          {isLoading ? <Loader2 className="w-6 h-6 animate-spin" /> : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-muted-foreground border-b">
                  <th className="py-2 pr-4 font-medium">Label</th><th className="py-2 px-2 font-medium">Prefix</th>
                  <th className="py-2 px-2 font-medium max-sm:hidden">Created</th><th className="py-2 px-2 font-medium max-md:hidden">Last used</th>
                  <th className="py-2 px-2 font-medium">Status</th><th className="py-2 px-2 font-medium">Action</th>
                </tr>
              </thead>
              <tbody>
                {tokens?.map((t) => (
                  <tr key={t.id} className="border-b last:border-0">
                    <td className="py-2 pr-4 font-medium">{t.name}</td>
                    <td className="py-2 px-2 font-mono text-xs">{t.token_prefix}…</td>
                    <td className="py-2 px-2 text-muted-foreground whitespace-nowrap max-sm:hidden">{new Date(t.created_at).toLocaleDateString()}</td>
                    <td className="py-2 px-2 text-muted-foreground whitespace-nowrap max-md:hidden">{t.last_used_at ? new Date(t.last_used_at).toLocaleString() : '—'}</td>
                    <td className="py-2 px-2">{t.revoked ? <span className="text-red-600 dark:text-red-400">revoked</span> : <span className="text-green-600 dark:text-green-400">active</span>}</td>
                    <td className="py-2 px-2">{!t.revoked && <Button size="sm" variant="outline" onClick={() => revoke.mutate(t.id)} disabled={revoke.isPending}>Revoke</Button>}</td>
                  </tr>
                ))}
                {!tokens?.length && <tr><td colSpan={6} className="py-4 text-muted-foreground">No tokens yet.</td></tr>}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
