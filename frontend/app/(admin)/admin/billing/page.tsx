'use client';
import { CreditCard } from 'lucide-react';

export default function BillingPage() {
  return (
    <div className="space-y-2">
      <h1 className="text-3xl font-bold flex items-center gap-2">
        <CreditCard className="w-7 h-7 text-primary" /> Billing
      </h1>
      <p className="text-slate-500">Subscription &amp; billing management is coming soon.</p>
    </div>
  );
}
