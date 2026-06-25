import Link from 'next/link';
import { ArrowRight } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

/** Titled card section with an optional "view all" link. Reusable container for
 *  recent-events / recent-activity / any list block. */
export function DashboardSection({
  title,
  action,
  children,
  className,
}: {
  title: string;
  action?: { label: string; href: string };
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <Card className={className}>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <CardTitle className="text-base">{title}</CardTitle>
        {action ? (
          <Link
            href={action.href}
            className="flex items-center gap-1 text-sm font-medium text-primary hover:underline"
          >
            {action.label} <ArrowRight className="h-3.5 w-3.5" aria-hidden />
          </Link>
        ) : null}
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}
