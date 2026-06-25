'use client';

/** Last-resort boundary for errors thrown in the root layout. Must render its
 *  own <html>/<body> because it replaces the entire document tree. */
export default function GlobalError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <html lang="en">
      <body style={{ fontFamily: 'system-ui, sans-serif', display: 'flex', minHeight: '100vh', alignItems: 'center', justifyContent: 'center', margin: 0 }}>
        <div style={{ textAlign: 'center', padding: 32 }}>
          <h1 style={{ fontSize: 24, marginBottom: 8 }}>Something went wrong</h1>
          <p style={{ color: '#666', marginBottom: 24 }}>{error.message || 'An unexpected error occurred.'}</p>
          <button
            onClick={reset}
            style={{ padding: '8px 16px', borderRadius: 8, border: '1px solid #ccc', background: '#fff', cursor: 'pointer' }}
          >
            Try again
          </button>
        </div>
      </body>
    </html>
  );
}
