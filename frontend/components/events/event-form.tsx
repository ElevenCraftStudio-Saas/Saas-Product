'use client';

import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { useCreateEvent } from '@/lib/hooks/events';

const schema = z.object({
  title: z.string().min(3, 'At least 3 characters'),
  description: z.string().optional(),
  event_date: z.string().min(1, 'Pick a date'),
});
type Values = z.infer<typeof schema>;

/** Create-event form. (Editing needs a backend PATCH /events — see report.) */
export function EventForm({ onDone }: { onDone?: () => void }) {
  const create = useCreateEvent();
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { title: '', description: '', event_date: '' },
  });

  async function onSubmit(values: Values) {
    await create.mutateAsync(values);
    form.reset();
    onDone?.();
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
        <FormField
          control={form.control}
          name="title"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Event title</FormLabel>
              <FormControl>
                <Input placeholder="Rahul &amp; Priya’s Wedding" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="event_date"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Event date</FormLabel>
              <FormControl>
                <Input type="date" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="description"
          render={({ field }) => (
            <FormItem>
              <FormLabel>
                Description <span className="text-muted-foreground">(optional)</span>
              </FormLabel>
              <FormControl>
                <Input placeholder="Venue, notes…" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <Button type="submit" className="w-full" disabled={create.isPending}>
          {create.isPending ? 'Creating…' : 'Create event'}
        </Button>
      </form>
    </Form>
  );
}
