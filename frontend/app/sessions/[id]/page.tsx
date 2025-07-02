'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { fetchSession, Session } from '../../../lib/api';
import { ParticipantManager } from '../../../components/ParticipantManager';
import { MeetingScheduler } from '../../../components/MeetingScheduler';
import { MeetingList } from '../../../components/MeetingList';
import { RecordingList } from '../../../components/RecordingList';

export default function SessionPage() {
  const { id: raw } = useParams();
  const [session, setSession] = useState<Session | null>(null);

  const [loadingLocal, setLoadingLocal] = useState(false);
  const [localStatus, setLocalStatus]   = useState<string | null>(null);
  const [localError, setLocalError]     = useState<string | null>(null);

  // Add a refreshKey state
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    if (!raw || Array.isArray(raw)) return;
    fetchSession(raw)
      .then(setSession)
      .catch(console.error);
  }, [raw]);

  if (!raw || Array.isArray(raw)) return <p>Invalid session ID</p>;
  if (!session)                      return <p>Loading…</p>;

  const handleArchive = async () => {
    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/sessions/${session.id}/store-recordings`,
        { method: 'POST' }
      );
      if (!res.ok) throw new Error(await res.text());
      const { stored } = await res.json();
      alert(`Uploaded ${stored.length} recordings to Azure`);
    } catch (err: any) {
      alert(`Archive failed: ${err.message}`);
    }
  };

  const handleDownloadLocal = async () => {
    setLoadingLocal(true);
    setLocalStatus(null);
    setLocalError(null);

    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/sessions/${session.id}/download-recordings-local`,
        { method: 'POST' }
      );
      if (!res.ok) throw new Error(await res.text());
      const json = await res.json();
      setLocalStatus(`Saved ${json.downloaded_files.length} files on server`);
    } catch (err: any) {
      setLocalError(err.message);
    } finally {
      setLoadingLocal(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="card">
        <h2 className="text-2xl font-semibold text-primary">{session.title}</h2>
        <p className="mt-2 text-gray-600">{session.description}</p>
      </div>

      <ParticipantManager
        sessionId={raw}
        existing={session.participants}
        onChange={plist => setSession({ ...session, participants: plist })}
      />

      {/* Pass onScheduled callback to MeetingScheduler */}
      <MeetingScheduler sessionId={raw} onScheduled={() => setRefreshKey(k => k + 1)} />
      {/* Pass refreshKey to MeetingList */}
      <MeetingList sessionId={raw} refreshKey={refreshKey} />
      <RecordingList sessionId={raw} />

      {/* Archive to Azure */}
      <div className="card mt-6">
        <button
          onClick={handleArchive}
          className="w-full bg-secondary text-white px-4 py-2 rounded hover:bg-primary transition-colors"
        >
          Archive Recordings to Azure
        </button>
      </div>

      {/* Download Locally */}
      <div className="card mt-4">
        <button
          onClick={handleDownloadLocal}
          disabled={loadingLocal}
          className={`w-full px-4 py-2 rounded text-white transition-colors ${
            loadingLocal
              ? 'bg-gray-400 cursor-not-allowed'
              : 'bg-green-600 hover:bg-green-700'
          }`}
        >
          {loadingLocal ? 'Downloading…' : 'Download Recordings Locally'}
        </button>
        {localStatus && <p className="text-green-600 mt-2">{localStatus}</p>}
        {localError  && <p className="text-red-600   mt-2">Error: {localError}</p>}
      </div>
    </div>
  );
}
