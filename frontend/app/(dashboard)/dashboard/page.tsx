'use client';

import { useQuery } from '@tanstack/react-query';
import api from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Plus, Calendar, Image as ImageIcon, QrCode } from 'lucide-react';
import Link from 'next/link';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import { toast } from 'sonner';

const eventSchema = z.object({
  title: z.string().min(3),
  description: z.string().optional(),
  event_date: z.string(),
});

export default function DashboardPage() {
  const [open, setOpen] = useState(false);
  const { data: events, refetch, isLoading } = useQuery({
    queryKey: ['events'],
    queryFn: async () => {
      const response = await api.get('/events/');
      return response.data;
    },
  });

  const form = useForm<z.infer<typeof eventSchema>>({
    resolver: zodResolver(eventSchema),
    defaultValues: {
      title: '',
      description: '',
      event_date: '',
    },
  });

  async function onSubmit(values: z.infer<typeof eventSchema>) {
    try {
      await api.post('/events/', {
        ...values,
        event_date: new Date(values.event_date).toISOString()
      });
      toast.success('Event created successfully');
      setOpen(false);
      refetch();
    } catch (error) {
      const detail = (error as { response?: { data?: { detail?: string } } })
        .response?.data?.detail;
      toast.error(detail || 'Failed to create event');
    }
  }

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Your Events</h1>
          <p className="text-slate-500">Manage your wedding galleries and QR codes</p>
        </div>
        
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger render={<Button className="space-x-2" />}>
            <Plus className="w-5 h-5" />
            <span>Create Event</span>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Create New Event</DialogTitle>
            </DialogHeader>
            <Form {...form}>
              <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
                <FormField
                  control={form.control}
                  name="title"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Event Title</FormLabel>
                      <FormControl>
                        <Input placeholder="Rahul & Priya's Wedding" {...field} />
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
                      <FormLabel>Event Date</FormLabel>
                      <FormControl>
                        <Input type="date" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <Button type="submit" className="w-full">Create Event</Button>
              </form>
            </Form>
          </DialogContent>
        </Dialog>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-48 bg-slate-200 animate-pulse rounded-xl"></div>
          ))}
        </div>
      ) : events?.length === 0 ? (
        <div className="text-center py-20 bg-white border border-dashed rounded-xl">
          <Calendar className="w-12 h-12 text-slate-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium">No events found</h3>
          <p className="text-slate-500 mb-6">Start by creating your first wedding event</p>
          <Button variant="outline" onClick={() => setOpen(true)}>Create Event</Button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {events?.map((event: { id: number; title: string; created_at: string }) => (
            <Link key={event.id} href={`/events/${event.id}`}>
              <Card className="hover:shadow-md transition-shadow cursor-pointer overflow-hidden group">
                <CardHeader className="bg-slate-50 border-b group-hover:bg-slate-100 transition-colors">
                  <CardTitle className="flex items-center justify-between">
                    <span className="truncate">{event.title}</span>
                    <Calendar className="w-4 h-4 text-slate-400" />
                  </CardTitle>
                </CardHeader>
                <CardContent className="pt-6">
                  <div className="flex items-center justify-between text-sm text-slate-600">
                    <div className="flex items-center space-x-2">
                      <ImageIcon className="w-4 h-4" />
                      <span>View Gallery</span>
                    </div>
                    <div className="flex items-center space-x-2">
                      <QrCode className="w-4 h-4" />
                      <span>QR Ready</span>
                    </div>
                  </div>
                  <div className="mt-4 pt-4 border-t text-xs text-slate-400" suppressHydrationWarning>
                    Created on {new Date(event.created_at).toLocaleDateString()}
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
