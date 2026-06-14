import { redirect } from 'next/navigation';

// The dashboard already renders the event list ("Your Events"); /events is an
// alias so the sidebar link resolves instead of 404-ing.
export default function EventsPage() {
  redirect('/dashboard');
}
