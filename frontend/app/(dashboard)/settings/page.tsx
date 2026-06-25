'use client';

import { PageHeader } from '@/components/layout/page-header';
import { Card, CardContent } from '@/components/ui/card';
import { ModeToggle } from '@/components/ui/mode-toggle';

export default function SettingsPage() {
  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <PageHeader title="Settings" description="Preferences for your studio account." />
      <Card>
        <CardContent className="flex items-center justify-between pt-6">
          <div>
            <p className="font-medium">Appearance</p>
            <p className="text-sm text-muted-foreground">Switch between light and dark mode.</p>
          </div>
          <ModeToggle />
        </CardContent>
      </Card>
      <p className="text-sm text-muted-foreground">More studio settings are coming soon.</p>
    </div>
  );
}
