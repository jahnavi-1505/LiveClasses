'use client';
import { useState } from 'react';
import { Participant, addParticipants, deleteParticipant } from '../lib/api';

export function ParticipantManager({
  sessionId,
  existing,
  onChange,
}: {
  sessionId: string;
  existing: Participant[];
  onChange: (plist: Participant[]) => void;
}) {
  const [emailList, setEmailList] = useState('');

  const handleAdd = async () => {
    const emails = emailList.split(',').map(e => e.trim()).filter(Boolean);
    if (!emails.length) return;
    const newParts = await addParticipants(sessionId, emails);
    onChange([...existing, ...newParts]);
    setEmailList('');
  };

  const handleRemove = async (id: string) => {
    await deleteParticipant(sessionId, id);
    onChange(existing.filter(p => p.id !== id));
  };

  return (
    <div className="space-y-2">
      <h4 className="font-semibold">Participants</h4>
      <ul className="pl-4 list-disc space-y-1">
        {existing.map(p => (
          <li key={p.id} className="flex justify-between items-center">
            <span>{p.email} ({p.role})</span>
            <button className="text-red-500" onClick={() => handleRemove(p.id)}>Remove</button>
          </li>
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