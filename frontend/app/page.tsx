'use client';

import { useEffect, useState } from 'react';
import { fetchSessions, createSession, deleteSession, Session } from '../lib/api';
import { SessionCard } from '../components/SessionCard';

export default function Home() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [title, setTitle] = useState('');
  const [desc, setDesc] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchSessions().then(setSessions);
  }, []);

  const handleAdd = async () => {
    if (!title.trim()) return alert('Title is required');
    setLoading(true);
    try {
      const s = await createSession(title, desc);
      setSessions([s, ...sessions]);
      setTitle('');
      setDesc('');
    } catch (e: any) {
      alert('Failed to create session: ' + e.message);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this session?')) return;
    try {
      await deleteSession(id);
      setSessions(sessions.filter(s => s.id !== id));
    } catch (e: any) {
      alert('Failed to delete session: ' + e.message);
    }
  };

  return (
    <div className="space-y-8">
      {/* Create New Session Card */}
      <div className="card">
        <h2 className="text-2xl font-bold text-primary">Create New Session</h2>
        <input
          className="mt-4 w-full border border-gray-300 rounded p-2 focus:outline-none focus:ring-2 focus:ring-secondary"
          placeholder="Title"
          value={title}
          onChange={e => setTitle(e.target.value)}
        />
        <textarea
          className="mt-2 w-full border border-gray-300 rounded p-2 h-24 focus:outline-none focus:ring-2 focus:ring-secondary"
          placeholder="Description"
          value={desc}
          onChange={e => setDesc(e.target.value)}
        />
        <button
          className="mt-4 bg-secondary text-white px-6 py-2 rounded hover:bg-primary transition-colors disabled:opacity-50"
          onClick={handleAdd}
          disabled={loading}
        >
          {loading ? 'Creating…' : 'Create Session'}
        </button>
      </div>

      {/* Existing Sessions */}
      <h2 className="text-2xl font-bold text-primary">Existing Sessions</h2>
      <div className="grid md:grid-cols-2 gap-6">
        {sessions.map(s => (
          <SessionCard
            key={s.id}
            session={s}
            onDelete={handleDelete}
          />
        ))}
      </div>
    </div>
  );
}
