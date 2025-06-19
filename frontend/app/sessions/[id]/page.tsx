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
  const [loadingInvites, setLoadingInvites] = useState(false);
  const [inviteStatus, setInviteStatus] = useState<string | null>(null);
  const [inviteError, setInviteError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      if (!raw || Array.isArray(raw)) return;
      const sess = await fetchSession(raw);
      setSession(sess);
    }
    load();
  }, [raw]);

  if (!raw || Array.isArray(raw)) return <p>Invalid session ID</p>;
  if (!session) return <p>Loading...</p>;

  const handleSendInvites = async () => {
    setLoadingInvites(true);
    setInviteStatus(null);
    setInviteError(null);
    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/sessions/${session.id}/send-invites`,
        { method: 'POST' }
      );
      if (!res.ok) throw new Error(await res.text());
      const json = await res.json();
      setInviteStatus(json.detail);
    } catch (e: any) {
      setInviteError(e.message);
    } finally {
      setLoadingInvites(false);
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

      <button
        className={`mt-4 px-4 py-2 rounded text-white transition-colors ${
          loadingInvites ? 'bg-gray-400 cursor-not-allowed' : 'bg-secondary hover:bg-primary'
        }`}
        onClick={handleSendInvites}
        disabled={loadingInvites}
      >
        {loadingInvites ? 'Sending Invites…' : 'Send Invite Email'}
      </button>
      {inviteStatus && <p className="text-green-600 mt-2">{inviteStatus}</p>}
      {inviteError && <p className="text-red-600 mt-2">Error: {inviteError}</p>}

      <MeetingScheduler sessionId={raw} />
      <MeetingList sessionId={raw} />
      <RecordingList sessionId={raw} />
    </div>
  );
}