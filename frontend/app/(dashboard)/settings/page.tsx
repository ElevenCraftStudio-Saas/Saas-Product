'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { KeyRound, Plus, Trash2, Copy, Loader2, ShieldAlert } from 'lucide-react';
import { toast } from 'sonner';

interface ApiToken {
  id: number;
  name: string | null;
  token_prefix: string | null;
  revoked: boolean;
  created_at: string;
  last_used_at: string | null;
}

export default function SettingsPage() {
  const qc = useQueryClient();
  const [name, setName] = useState('');
  const [newToken, setNewToken] = useState<string | null>(null);

  const { data: tokens, isLoading } = useQuery<ApiToken[]>({
    queryKey: ['api-tokens'],
    queryFn: async () => (await api.get('/auth/tokens')).data,
  });

  const create = useMutation({
    mutationFn: async (n: string) => (await api.post('/auth/tokens', { name: n })).data,
    onSuccess: (d: { token: string }) => {
      setNewToken(d.token);
      setName('');
      qc.invalidateQueries({ queryKey: ['api-tokens'] });
    },
    onError: () => toast.error('Could not create key'),
  });

  const revoke = useMutation({
    mutationFn: async (id: number) => api.delete(`/auth/tokens/${id}`),
    onSuccess: () => {
      toast.success('Key revoked');
      qc.invalidateQueries({ queryKey: ['api-tokens'] });
    },
    onError: () => toast.error('Could not revoke key'),
  });

  function copy(text: string) {
    navigator.clipboard.writeText(text);
    toast.success('Copied to clipboard');
  }

  return (
    <div className="max-w-3xl space-y-8">
      <div>
        <h1 className="text-3xl font-bold flex items-center gap-2">
          <KeyRound className="w-7 h-7 text-primary" /> API Keys
        </h1>
        <p className="text-slate-500 mt-1">
          Keys authenticate the <b>Desktop Ingest Agent</b> for zero-touch photo upload.
        </p>
      </div>

      {/* Newly created token — shown once */}
      {newToken && (
        <Card className="border-amber-300 bg-amber-50">
          <CardContent className="pt-6 space-y-3">
            <p className="flex items-center gap-2 text-amber-800 font-medium">
              <ShieldAlert className="w-5 h-5" /> Copy this key now — it won&apos;t be shown again.
            </p>
            <div className="flex gap-2">
              <code className="flex-1 bg-white border rounded px-3 py-2 text-sm font-mono break-all">
                {newToken}
              </code>
              <Button variant="outline" onClick={() => copy(newToken)}>
                <Copy className="w-4 h-4" />
              </Button>
            </div>
            <Button variant="ghost" size="sm" onClick={() => setNewToken(null)}>
              Done
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Create */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Create a key</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex gap-2">
            <Input
              placeholder="Key name (e.g. Studio laptop)"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
            <Button onClick={() => create.mutate(name || 'agent')} disabled={create.isPending}>
              {create.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
              <span className="ml-1">Create</span>
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* List */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Your keys</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <Loader2 className="w-5 h-5 animate-spin" />
          ) : !tokens?.length ? (
            <p className="text-sm text-slate-400">No keys yet.</p>
          ) : (
            <div className="divide-y">
              {tokens.map((t) => (
                <div key={t.id} className="flex items-center justify-between py-3">
                  <div className="min-w-0">
                    <p className="font-medium truncate">
                      {t.name || 'agent'}{' '}
                      {t.revoked && <span className="text-xs text-red-500">(revoked)</span>}
                    </p>
                    <p className="text-xs text-slate-400 font-mono">
                      {t.token_prefix}…··· · created {new Date(t.created_at).toLocaleDateString()} ·{' '}
                      last used {t.last_used_at ? new Date(t.last_used_at).toLocaleString() : 'never'}
                    </p>
                  </div>
                  {!t.revoked && (
                    <Button
                      variant="ghost"
                      size="icon"
                      className="text-red-500 hover:text-red-600 hover:bg-red-50"
                      onClick={() => revoke.mutate(t.id)}
                      disabled={revoke.isPending}
                    >
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
