'use client';
import Link from 'next/link';
import React from 'react';
import { Session } from '../lib/api';

interface Props {
  session: Session;
  onDelete?: (id: string) => Promise<void>;
}

export function SessionCard({ session, onDelete }: Props) {
  const date = new Date(session.created_at).toLocaleDateString();

  return (
    <div className="card relative hover:shadow-xl transition-shadow">
      <Link
        href={`/sessions/${session.id}`}
        className="block"
      >
        <h3 className="text-xl font-semibold text-primary">{session.title}</h3>
        <p className="text-gray-600 mt-2">{session.description}</p>
        <p className="text-sm text-gray-400 mt-4">Created on {date}</p>
      </Link>

      {onDelete && (
        <button
          onClick={() => onDelete(session.id)}
          className="absolute top-2 right-2 text-red-500 hover:text-red-700"
          title="Delete session"
        >
          🗑️
        </button>
      )}
    </div>
  );
}
