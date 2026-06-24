'use client';
import { Settings } from 'lucide-react';

export default function StudioSettingsPage() {
  return (
    <div className="space-y-2">
      <h1 className="text-3xl font-bold flex items-center gap-2">
        <Settings className="w-7 h-7 text-primary" /> Studio Settings
      </h1>
      <p className="text-slate-500">Studio-wide settings are coming soon.</p>
    </div>
  );
}
