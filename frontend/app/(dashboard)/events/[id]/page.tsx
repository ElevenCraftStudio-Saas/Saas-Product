/* eslint-disable */
'use client';

import { useQuery } from '@tanstack/react-query';
import { useParams, useRouter } from 'next/navigation';
import api from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Upload, QrCode, ArrowLeft, Download, CheckCircle2, Clock, XCircle, Loader2 } from 'lucide-react';
import Link from 'next/link';
import { useState, useCallback } from 'react';
import { toast } from 'sonner';
import { Progress } from '@/components/ui/progress';
import { FolderWatch } from '@/components/dashboard/folder-watch';

export default function EventDetailsPage() {
  const { id } = useParams();
  const router = useRouter();
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);

  const { data: event, isLoading: eventLoading } = useQuery({
    queryKey: ['event', id],
    queryFn: async () => {
      const response = await api.get(`/events/${id}`);
      return response.data;
    },
  });

  const { data: photos, refetch: refetchPhotos } = useQuery({
    queryKey: ['photos', id],
    queryFn: async () => {
      const response = await api.get(`/photos/event/${id}`);
      return response.data;
    },
    refetchInterval: 5000, // Poll every 5 seconds for processing status
  });

  const onUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files?.length) return;
    
    setUploading(true);
    const files = Array.from(e.target.files);
    const formData = new FormData();
    files.forEach(file => formData.append('files', file));

    try {
      await api.post(`/photos/upload/${id}`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (progressEvent) => {
          const percentCompleted = Math.round((progressEvent.loaded * 100) / (progressEvent.total || 1));
          setProgress(percentCompleted);
        }
      });
      toast.success('Photos uploaded successfully. AI processing started.');
      refetchPhotos();
    } catch (error) {
      toast.error('Upload failed');
    } finally {
      setUploading(false);
      setProgress(0);
    }
  };

  if (eventLoading) return <div className="flex items-center justify-center h-64"><Loader2 className="w-8 h-8 animate-spin" /></div>;

  return (
    <div className="space-y-8">
      <div className="flex items-center space-x-4">
        <Link href="/dashboard">
          <Button variant="outline" size="icon">
            <ArrowLeft className="w-4 h-4" />
          </Button>
        </Link>
        <div>
          <h1 className="text-3xl font-bold">{event?.title}</h1>
          <p className="text-slate-500">Event Slug: {event?.event_slug}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* QR Code Section */}
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <QrCode className="w-5 h-5" />
              <span>Event QR Code</span>
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col items-center">
            {event?.url ? (
              <div className="bg-white p-4 rounded-xl border mb-4">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={event.url}
                  alt="QR Code"
                  className="w-48 h-48"
                />
              </div>
            ) : (
              <div className="w-48 h-48 bg-slate-100 animate-pulse rounded-xl mb-4"></div>
            )}
            <p className="text-sm text-center text-slate-500 mb-6">
              Guests can scan this code to find their photos instantly.
            </p>
            <Button
              variant="outline"
              className="w-full space-x-2"
              disabled={!event?.url}
              onClick={() => event?.url && window.open(event.url, '_blank')}
            >
              <Download className="w-4 h-4" />
              <span>Download QR</span>
            </Button>
          </CardContent>
        </Card>

        {/* Upload Section */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <Upload className="w-5 h-5" />
              <span>Upload Wedding Photos</span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="border-2 border-dashed rounded-xl p-10 flex flex-col items-center justify-center space-y-4 bg-slate-50/50 hover:bg-slate-50 transition-colors cursor-pointer relative">
              <input 
                type="file" 
                multiple 
                accept="image/*" 
                className="absolute inset-0 opacity-0 cursor-pointer" 
                onChange={onUpload}
                disabled={uploading}
              />
              <div className="w-12 h-12 bg-primary/10 rounded-full flex items-center justify-center">
                <Upload className="w-6 h-6 text-primary" />
              </div>
              <div className="text-center">
                <p className="font-medium">Click or drag photos to upload</p>
                <p className="text-xs text-slate-500 mt-1">PNG, JPG, JPEG up to 10MB each</p>
              </div>
            </div>
            
            {uploading && (
              <div className="mt-6 space-y-2">
                <div className="flex justify-between text-sm">
                  <span>Uploading photos...</span>
                  <span>{progress}%</span>
                </div>
                <Progress value={progress} className="h-2" />
              </div>
            )}

            <div className="mt-8">
              <h3 className="font-semibold mb-4">Recent Uploads ({photos?.length || 0})</h3>
              <div className="grid grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
                {photos?.map((photo: any) => (
                  <div key={photo.id} className="relative group aspect-square rounded-lg overflow-hidden border bg-slate-100">
                    <img 
                      src={photo.url?.startsWith('/') ? `http://localhost:8000${photo.url}` : photo.url} 
                      alt={photo.filename}
                      className="w-full h-full object-cover"
                    />
                    <div className="absolute top-1 right-1">
                      {photo.processing_status === 'completed' && <CheckCircle2 className="w-4 h-4 text-green-500 fill-white" />}
                      {photo.processing_status === 'pending' && <Clock className="w-4 h-4 text-amber-500 fill-white" />}
                      {photo.processing_status === 'processing' && <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />}
                      {photo.processing_status === 'failed' && <XCircle className="w-4 h-4 text-red-500 fill-white" />}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Auto folder upload (watchdog) */}
        <FolderWatch eventId={id as string} />
      </div>
    </div>
  );
}
