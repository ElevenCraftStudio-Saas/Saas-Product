import {
  LayoutDashboard,
  Users,
  KeyRound,
  ScrollText,
  BarChart3,
  Calendar,
  User,
  Settings,
  type LucideIcon,
} from 'lucide-react';
import type { Role } from '@/types/models';

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  /** Exact match for index routes (e.g. /admin); else active on prefix. */
  exact?: boolean;
}

export const adminNav: NavItem[] = [
  { href: '/admin', label: 'Dashboard', icon: LayoutDashboard, exact: true },
  { href: '/admin/users', label: 'Users', icon: Users },
  { href: '/admin/tokens', label: 'Agent Tokens', icon: KeyRound },
  { href: '/admin/audit', label: 'Audit Log', icon: ScrollText },
  { href: '/admin/analytics', label: 'Analytics', icon: BarChart3 },
];

// Studio user nav. Folder-watch + API tokens are admin-gated in the backend
// (require_admin) — intentionally NOT here. Photo upload happens inside an event.
export const studioNav: NavItem[] = [
  { href: '/dashboard', label: 'Dashboard', icon: LayoutDashboard, exact: true },
  { href: '/events', label: 'Events', icon: Calendar },
  { href: '/profile', label: 'Profile', icon: User },
  { href: '/settings', label: 'Settings', icon: Settings },
];

export function navForRole(role: Role): NavItem[] {
  return role === 'admin' ? adminNav : studioNav;
}

/** Active when the current path matches the item (exact or prefix). */
export function isNavItemActive(pathname: string, item: NavItem): boolean {
  return item.exact ? pathname === item.href : pathname === item.href || pathname.startsWith(`${item.href}/`);
}
