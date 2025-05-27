'use client';
import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { fetchSession, Session } from '../../../lib/api';
import { ParticipantManager } from '../../../components/ParticipantManager';
import { MeetingScheduler } from '../../../components/MeetingScheduler';

export default function SessionPage() {
  const { id: raw } = useParams()
  const [session, setSession] = useState<Session | null>(null)

  useEffect(() => {
    async function load() {
      if (!raw || Array.isArray(raw)) return
      const sess = await fetchSession(raw)
      setSession(sess)
    }
    load()
  }, [raw])

  if (!raw || Array.isArray(raw)) return <p>Invalid session ID</p>
  if (!session) return <p>Loading...</p>

  return (
    <div className="space-y-6">
      <h2 className="text-2xl">{session.title}</h2>
      <p>{session.description}</p>

      <ParticipantManager
        sessionId={raw}
        existing={session.participants}
        onChange={plist => setSession({ ...session, participants: plist })}
      />

      <MeetingScheduler sessionId={raw} />
    </div>
  )
}