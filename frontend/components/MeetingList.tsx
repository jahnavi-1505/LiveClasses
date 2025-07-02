'use client';
import { Meeting, fetchMeetings, updateMeeting } from '../lib/api';
import { useEffect, useState } from 'react';
import DatePicker from 'react-datepicker';
import 'react-datepicker/dist/react-datepicker.css';

export function MeetingList({ sessionId, refreshKey }: { sessionId: string, refreshKey?: number }) {
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [editing, setEditing] = useState<string | null>(null);
  const [newDate, setNewDate] = useState<Date | null>(null);

  useEffect(() => {
    fetchMeetings(sessionId).then(setMeetings);
  }, [sessionId, refreshKey]);

  const save = async (id: string) => {
    if (!newDate) return;
    const iso = newDate.toISOString();
    const updated = await updateMeeting(sessionId, id, iso);
    setMeetings(ms => ms.map(m => m.id === id ? updated : m));
    setEditing(null);
  };

  return (
    <div className="space-y-4">
      <h4 className="font-semibold">Meetings</h4>
      {meetings.map(m => (
        <div key={m.id} className="border p-2 rounded">
          <p>Join URL: <a href={m.join_url} target="_blank" className="text-blue-600 hover:underline">{m.join_url}</a></p>
          <p>Scheduled: {new Date(m.scheduled_for).toLocaleString()}</p>
          {editing === m.id ? (
            <div className="mt-2 flex space-x-2">
              <DatePicker
                selected={newDate}
                onChange={d => setNewDate(d)}
                showTimeSelect
                dateFormat="Pp"
                className="border p-1"
              />
              <button className="bg-green-500 text-white px-2" onClick={() => save(m.id)}>Save</button>
              <button className="bg-gray-300 px-2" onClick={() => setEditing(null)}>Cancel</button>
            </div>
          ) : (
            <button className="mt-2 bg-yellow-500 px-2" onClick={() => { setEditing(m.id); setNewDate(new Date(m.scheduled_for)); }}>
              Edit Time
            </button>
          )}
        </div>
      ))}
    </div>
  );
}