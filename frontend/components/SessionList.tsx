// components/SessionList.tsx
'use client'

import Link from 'next/link'
import { Session } from '../lib/api'

export function SessionList({
  sessions,
  onDelete,
}: {
  sessions: Session[]
  onDelete?: (id: string) => Promise<void>
}) {
  return (
    <ul className="space-y-2">
      {sessions.map((s) => (
        <li
          key={s.id}
          className="flex justify-between items-center border p-2 rounded"
        >
          <Link
            href={`/sessions/${s.id}`}
            className="text-blue-600 hover:underline flex-1"
          >
            {s.title}
          </Link>
          {onDelete && (
            <button
              className="ml-4 text-red-500 hover:underline"
              onClick={() => onDelete(s.id)}
            >
              Delete
            </button>
          )}
        </li>
      ))}
    </ul>
  )
}
