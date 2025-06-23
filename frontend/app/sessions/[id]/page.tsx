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

  useEffect(() => {
    if (!raw || Array.isArray(raw)) return;
    fetchSession(raw).then(setSession).catch(console.error);
  }, [raw]);

  if (!raw || Array.isArray(raw)) return <p>Invalid session ID</p>;
  if (!session) return <p>Loading…</p>;

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

      <MeetingScheduler sessionId={raw} />
      <MeetingList sessionId={raw} />
      <RecordingList sessionId={raw} />

      {/* archive button inside its own card for contrast */}
      <div className="w-full bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 transition">
        <button
          onClick={handleArchive}
          className="w-full bg-secondary text-white px-4 py-2 rounded hover:bg-primary transition-colors"
        >
          Archive Recordings to Azure
        </button>
      </div>
    </div>
  );
}
