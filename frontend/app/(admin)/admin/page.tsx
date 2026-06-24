import { redirect } from 'next/navigation';

// /admin landing → user management.
export default function AdminIndex() {
  redirect('/admin/users');
}
