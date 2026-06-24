'use client';

import { useRouter } from 'next/navigation';
import { useEffect } from 'react';
import Link from 'next/link';
import { Camera, LayoutDashboard, Calendar, LogOut, Menu } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/lib/auth-context';
import { useMe } from '@/lib/hooks/me';

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const { user, loading, signOut } = useAuth();
  const { data: me, isLoading: meLoading } = useMe();

  useEffect(() => {
    if (!loading && !user) { router.push('/login'); return; }
    if (me && me.role !== 'user') router.push(me.role === 'admin' ? '/admin' : '/pending');
  }, [loading, user, me, router]);

  const handleLogout = async () => {
    await signOut();
    router.push('/login');
  };

  if (loading || !user || meLoading || !me || me.role !== 'user') {
    return null; // Avoid flashing dashboard before auth/role resolves
  }

  return (
    <div className="flex h-screen bg-slate-50">
      {/* Sidebar */}
      <aside className="w-64 bg-white border-r hidden md:flex flex-col">
        <div className="p-6 border-b">
          <Link href="/dashboard" className="flex items-center space-x-2">
            <Camera className="w-8 h-8 text-primary" />
            <span className="text-xl font-bold">WedFind AI</span>
          </Link>
        </div>
        <nav className="flex-1 p-4 space-y-2">
          <Link href="/dashboard">
            <Button variant="ghost" className="w-full justify-start space-x-2">
              <LayoutDashboard className="w-5 h-5" />
              <span>Dashboard</span>
            </Button>
          </Link>
          <Link href="/events">
            <Button variant="ghost" className="w-full justify-start space-x-2">
              <Calendar className="w-5 h-5" />
              <span>Events</span>
            </Button>
          </Link>
        </nav>
        <div className="p-4 border-t">
          <Button 
            variant="ghost" 
            className="w-full justify-start space-x-2 text-red-500 hover:text-red-600 hover:bg-red-50"
            onClick={handleLogout}
          >
            <LogOut className="w-5 h-5" />
            <span>Logout</span>
          </Button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col overflow-hidden">
        <header className="h-16 bg-white border-b flex items-center justify-between px-6 md:px-8">
          <div className="md:hidden flex items-center">
            <Menu className="w-6 h-6 mr-4" />
            <span className="font-bold">WedFind AI</span>
          </div>
          <div className="flex-1"></div>
          <div className="flex items-center space-x-4">
            <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center text-primary font-bold">
              A
            </div>
            <span className="text-sm font-medium">Admin Photographer</span>
          </div>
        </header>
        <section className="flex-1 overflow-y-auto p-6 md:p-8">
          {children}
        </section>
      </main>
    </div>
  );
}
