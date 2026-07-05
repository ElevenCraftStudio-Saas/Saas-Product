'use client';

import { useEffect, useState } from 'react';

interface ProcessingState {
  type: 'progress' | 'completed' | 'error' | 'timeout';
  status: string;
  message: string;
  progress: number;
  count?: number;
  photos?: Array<{ id: number; filename: string; url: string; download_token: string }>;
}

const TERMINAL_TYPES = new Set(['completed', 'error', 'timeout']);

/** The API lives on its own origin — EventSource can't use the axios instance,
 *  so build the absolute URL from the same env the axios baseURL uses. */
function streamUrl(slug: string, requestId: string): string {
  const base = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api').replace(/\/$/, '');
  return `${base}/guest/${slug}/processing-stream?request_id=${encodeURIComponent(requestId)}`;
}

export function useProcessingStream(slug: string, enabled: boolean, requestId: string) {
  const [state, setState] = useState<ProcessingState | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!enabled || !slug || !requestId) return;

    let done = false;
    const eventSource = new EventSource(streamUrl(slug, requestId));

    // EventSource has no native timeout — close it ourselves if no terminal
    // frame ever arrives (server caps streams at 60s; 65s = server cap + slack).
    const timeoutId = setTimeout(() => {
      if (!done) {
        done = true;
        eventSource.close();
        setError('Processing timed out. Please try again.');
      }
    }, 65000);

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as ProcessingState;
        setState(data);

        if (TERMINAL_TYPES.has(data.type)) {
          // Server ends the stream after a terminal frame; close before the
          // browser's auto-reconnect kicks in.
          done = true;
          eventSource.close();
          if (data.type === 'error') setError(data.message);
          if (data.type === 'timeout') setError('Processing timed out. Please try again.');
        }
      } catch (e) {
        console.error('Failed to parse SSE data:', e);
      }
    };

    eventSource.onerror = (err) => {
      // Fires on normal server-side stream close too — only a real error if
      // we never saw a terminal frame.
      eventSource.close();
      if (!done) {
        console.error('SSE error:', err);
        done = true;
        setError('Connection lost');
      }
    };

    return () => {
      clearTimeout(timeoutId);
      eventSource.close();
    };
  }, [slug, requestId, enabled]);

  return { state, error };
}
