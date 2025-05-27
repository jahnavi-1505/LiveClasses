'use client'

import { useState, useEffect } from 'react'
import DatePicker from 'react-datepicker'
import 'react-datepicker/dist/react-datepicker.css'
import { scheduleMeeting, fetchSession, Meeting } from '../lib/api'

/**
 * If a meeting already exists, display its join_url and reuse it.
 * Otherwise, allow scheduling a new meeting.
 */
export function MeetingScheduler({ sessionId }: { sessionId: string }) {
  const [date, setDate] = useState<Date | null>(null)
  const [existing, setExisting] = useState<Meeting | null>(null)
  const [loading, setLoading] = useState(true)

  // On mount, fetch session to see if a meeting already exists
  useEffect(() => {
    async function load() {
      const sess = await fetchSession(sessionId)
      if (sess.meetings && sess.meetings.length > 0) {
        setExisting(sess.meetings[0])
      }
      setLoading(false)
    }
    load()
  }, [sessionId])

  const handle = async () => {
    if (!date) return alert('Pick a date')
    const iso = date.toISOString()
    const meeting = await scheduleMeeting(sessionId, iso)
    setExisting(meeting)
    alert(`Meeting created!`)
  }

  if (loading) return <p>Loading meeting info...</p>

  return (
    <div className="space-y-2">
      {existing ? (
        <div>
          <h4 className="font-semibold">Meeting Link</h4>
          <p>
            <a
              href={existing.join_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-600 hover:underline"
            >
              {existing.join_url}
            </a>
          </p>
        </div>
      ) : (
        <>
          <h4 className="font-semibold">Schedule Meeting</h4>
          <div className="flex space-x-2">
            <DatePicker
              selected={date}
              onChange={d => setDate(d)}
              showTimeSelect
              dateFormat="Pp"
              className="border p-2"
              placeholderText="Select date & time"
            />
            <button
              className="bg-blue-500 text-white px-4 py-2 rounded"
              onClick={handle}
            >
              Schedule
            </button>
          </div>
        </>
      )}
    </div>
  )
}