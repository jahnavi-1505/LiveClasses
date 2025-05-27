'use client';
import Link from 'next/link';
import { Session } from '../lib/api';

export function SessionList({ sessions }: { sessions: Session[] }) {
  return (
    <ul className="space-y-2">
      {sessions.map(s => (
        <li key={s.id} className="flex justify-between">
          <Link href={`/sessions/${s.id}`} className="text-blue-600 hover:underline">
            {s.title}
          </Link>
          <span className="text-sm text-gray-500">{new Date(s.created_at).toLocaleString()}</span>
        </li>
      ))}
    </ul>
  );
}