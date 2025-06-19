'use client';
import { useEffect, useState } from 'react';
import { fetchRecordings, Recording } from '../lib/api';

export function RecordingList({ sessionId }: { sessionId: string }) {
  const [recs, setRecs] = useState<Recording[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const data = await fetchRecordings(sessionId);
        setRecs(data);
      } catch (e: any) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [sessionId]);

  if (loading) return <p>Loading recordings…</p>;
  if (error) return <p className="text-red-500">Error: {error}</p>;
  if (recs.length === 0) return <p>No recordings yet</p>;

  return (
    <div className="card">
      <h3 className="text-xl font-semibold text-primary mb-2">Recordings</h3>
      <ul className="list-disc pl-6 space-y-1">
        {recs.map(r => (
          <li key={`${r.meeting_id}-${r.id}`}>  
            <a
              href={r.download_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-secondary underline"
            >
              {new Date(r.recording_start).toLocaleString()} ({r.file_type})
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}