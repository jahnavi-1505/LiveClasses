'use client';
import { useState } from 'react';
import { Participant, addParticipants } from '../lib/api';

export function ParticipantManager({
  sessionId,
  existing,
  onChange,
}: {
  sessionId: string;
  existing: Participant[];
  onChange: (p: Participant[]) => void;
}) {
  const [emailList, setEmailList] = useState('');

  const handleAdd = async () => {
    const emails = emailList.split(',').map(e => e.trim()).filter(Boolean);
    if (!emails.length) return;
    const newParts = await addParticipants(sessionId, emails);
    onChange([...existing, ...newParts]);
    setEmailList('');
  };

  return (
    <div className="space-y-2">
      <h4 className="font-semibold">Participants</h4>
      <ul className="pl-4 list-disc space-y-1">
        {existing.map(p => (
          <li key={p.id}>{p.email} ({p.role})</li>
        ))}
      </ul>
      <div className="flex space-x-2">
        <input
          type="text"
          placeholder="comma-separated emails"
          className="border p-2 flex-1"
          value={emailList}
          onChange={e => setEmailList(e.target.value)}
        />
        <button className="bg-green-500 text-white px-4 py-2 rounded" onClick={handleAdd}>
          Add
        </button>
      </div>
    </div>
  );
}