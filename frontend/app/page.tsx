'use client'

import { useEffect, useState } from 'react'
import {
  fetchSessions,
  createSession,
  deleteSession,
  Session,
} from '../lib/api'
import { SessionList } from '../components/SessionList'

export default function Home() {
  const [sessions, setSessions] = useState<Session[]>([])
  const [title, setTitle] = useState('')
  const [desc, setDesc] = useState('')

  useEffect(() => {
    fetchSessions().then(setSessions)
  }, [])

  const add = async () => {
    const s = await createSession(title, desc)
    setSessions((prev) => [...prev, s])
    setTitle('')
    setDesc('')
  }

  const remove = async (id: string) => {
    if (!confirm('Are you sure you want to delete this session?')) return
    await deleteSession(id)
    setSessions((prev) => prev.filter((s) => s.id !== id))
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl">Create Session</h2>
        <input
          className="border p-2 mr-2"
          placeholder="Title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />
        <input
          className="border p-2 mr-2"
          placeholder="Description"
          value={desc}
          onChange={(e) => setDesc(e.target.value)}
        />
        <button
          className="bg-green-500 text-white px-4 py-2 rounded"
          onClick={add}
        >
          Create
        </button>
      </div>

      <div>
        <h2 className="text-xl">Sessions</h2>
        <SessionList sessions={sessions} onDelete={remove} />
      </div>
    </div>
  )
}
