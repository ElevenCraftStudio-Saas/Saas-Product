'use client';

import { useEffect, useState } from 'react';

interface ProcessingState {
  type: 'progress' | 'completed' | 'error' | 'timeout';
  status: string;
  message: string;
  progress: number;
  count?: number;
  photos?: Array<{ id: number; filename: string; url: string }>;
}

export function useProcessingStream(slug: string, enabled: boolean, requestId: string) {
  const [state, setState] = useState<ProcessingState | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!enabled || !slug || !requestId) return;

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 65000); // 65s timeout

    const eventSource = new EventSource(
      `/api/guest/${slug}/processing-stream?request_id=${encodeURIComponent(requestId)}`
    );

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as ProcessingState;
        setState(data);

        if (data.type === 'error') {
          setError(data.message);
        }
      } catch (e) {
        console.error('Failed to parse SSE data:', e);
      }
    };

    eventSource.onerror = (err) => {
      console.error('SSE error:', err);
      eventSource.close();
      setError('Connection lost');
    };

    return () => {
      clearTimeout(timeoutId);
      eventSource.close();
    };
  }, [slug, requestId, enabled]);

  return { state, error };
}
