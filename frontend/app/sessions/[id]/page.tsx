'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { fetchSession, Session } from '../../../lib/api';
import { ParticipantManager } from '../../../components/ParticipantManager';
import { MeetingScheduler } from '../../../components/MeetingScheduler';
import { MeetingList } from '../../../components/MeetingList';

export default function SessionPage() {
  const { id: raw } = useParams();
  const [session, setSession] = useState<Session | null>(null);
  const [loadingInvites, setLoadingInvites] = useState(false);
  const [inviteStatus, setInviteStatus] = useState<string | null>(null);
  const [inviteError, setInviteError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      if (!raw || Array.isArray(raw)) return;
      try {
        const sess = await fetchSession(raw);
        setSession(sess);
      } catch (e: any) {
        console.error('Failed to fetch session:', e);
      }
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
      if (!res.ok) {
        const text = await res.text();
        throw new Error(`Server returned ${res.status}: ${text}`);
      }
      const json = await res.json();
      setInviteStatus(json.detail || 'Invites sent successfully!');
    } catch (err: any) {
      console.error('Error sending invites:', err);
      setInviteError(err.message || 'Unknown error');
    } finally {
      setLoadingInvites(false);
    }
  };

  return (
    <div className="space-y-6">
      <h2 className="text-2xl">{session.title}</h2>
      <p>{session.description}</p>

      <ParticipantManager
        sessionId={raw}
        existing={session.participants}
        onChange={(plist) =>
          setSession((prev) =>
            prev ? { ...prev, participants: plist } : prev
          )
        }
      />

      <button
        className={`mt-4 px-4 py-2 rounded text-white ${
          loadingInvites ? 'bg-gray-400 cursor-not-allowed' : 'bg-purple-500 hover:bg-purple-600'
        }`}
        onClick={handleSendInvites}
        disabled={loadingInvites}
      >
        {loadingInvites ? 'Sending Invites…' : 'Send Invite Email'}
      </button>

      {inviteStatus && (
        <p className="mt-2 text-green-600">{inviteStatus}</p>
      )}
      {inviteError && (
        <p className="mt-2 text-red-600">Error: {inviteError}</p>
      )}

      <MeetingScheduler sessionId={raw} />

      <MeetingList sessionId={raw} />
    </div>
  );
}
