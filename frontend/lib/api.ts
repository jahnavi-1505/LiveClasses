const API = process.env.NEXT_PUBLIC_API_URL;

export type Participant = { id: string; email: string; role: string };
export type Meeting   = { id: string; join_url: string; scheduled_for: string };
export type Session   = {
  id: string;
  title: string;
  description?: string;
  created_at: string;
  participants: Participant[];
  meetings: Meeting[];
};

function check(res: Response) {
  if (!res.ok) throw new Error(res.statusText);
  return res.json();
}

export async function fetchSessions(): Promise<Session[]> {
  return fetch(`${API}/sessions`).then(check);
}

export async function fetchSession(id: string): Promise<Session> {
  return fetch(`${API}/sessions/${id}`).then(check);
}

export async function createSession(
  title: string,
  description?: string
): Promise<Session> {
  return fetch(`${API}/sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, description }),
  }).then(check);
}

// lib/api.ts
export async function deleteSession(id: string): Promise<void> {
  const res = await fetch(`${API}/sessions/${id}`, { method: 'DELETE' });
  if (!res.ok) throw new Error(res.statusText);
}


export async function addParticipants(
  sessionId: string,
  emails: string[],
  role: string = 'student'
): Promise<Participant[]> {
  return fetch(`${API}/sessions/${sessionId}/participants`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ emails, role }),
  }).then(check);
}

export async function scheduleMeeting(
  sessionId: string,
  scheduled_for: string
): Promise<Meeting> {
  return fetch(`${API}/sessions/${sessionId}/meetings`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ scheduled_for }),
  }).then(check);
}
export async function deleteParticipant(
  sessionId: string,
  participantId: string
): Promise<void> {
  await fetch(`${API}/sessions/${sessionId}/participants/${participantId}`, {
    method: 'DELETE'
  });
}
export async function fetchMeetings(
  sessionId: string
): Promise<Meeting[]> {
  return fetch(`${API}/sessions/${sessionId}/meetings`).then(check);
}
export async function fetchMeeting(
  sessionId: string,
  meetingId: string
): Promise<Meeting> {
  return fetch(`${API}/sessions/${sessionId}/meetings/${meetingId}`).then(check);
}
export async function updateMeeting(
  sessionId: string,
  meetingId: string,
  scheduled_for: string
): Promise<Meeting> {
  const res = await fetch(
    `${API}/sessions/${sessionId}/meetings/${meetingId}`,
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scheduled_for })
    }
  );
  if (!res.ok) throw new Error(res.statusText);
  return res.json();
}
