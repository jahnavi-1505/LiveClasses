"use client";

import { useEffect, useState } from "react";

/* ------------------------------------------------------------------------- */
/* Types                                                                    */
/* ------------------------------------------------------------------------- */

interface RecordingBase {
  /** Zoom’s per-file UID (may be undefined for some asset types) */
  file_id?: string;
  meeting_id: string;
  file_type: string;
  download_url: string;
  recording_start: string;
  recording_end: string;
}

interface RecordingWithStream extends RecordingBase {
  /** Pre-signed / SAS URL you can stream directly */
  stream_url: string;
}

interface RecordingListProps {
  sessionId: string;
  /** bump this value to force a re-fetch without remounting */
  refreshKey?: number;
}

/* ------------------------------------------------------------------------- */
/* Component                                                                */
/* ------------------------------------------------------------------------- */

export function RecordingList({
  sessionId,
  refreshKey,
}: RecordingListProps) {
  const [recs, setRecs] = useState<RecordingWithStream[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /* --------------------------- fetch on mount / change ------------------- */
  useEffect(() => {
    const abort = new AbortController();

    (async () => {
      setLoading(true);
      setError(null);

      try {
        const base =
          process.env.NEXT_PUBLIC_API ?? "http://localhost:8000";
        const url = `${base}/sessions/${sessionId}/recordings/stream_urls`;

        const res = await fetch(url, { signal: abort.signal });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);

        const json = await res.json();
        // your endpoint should return { recordings_with_streams: [...] }
        setRecs(json.recordings_with_streams ?? []);
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError")
          return; // unmounted
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setLoading(false);
      }
    })();

    return () => abort.abort();
  }, [sessionId, refreshKey]);

  /* --------------------------- render helpers ---------------------------- */
  if (loading) return <p>Loading recordings…</p>;
  if (error) return <p className="text-red-500">Error: {error}</p>;
  if (recs.length === 0)
    return <p>No recordings available for streaming yet.</p>;

  const keyFor = (r: RecordingWithStream, idx: number, prefix = "") =>
    `${prefix}${r.meeting_id}-${r.file_id ?? idx}`;

  /* --------------------------- UI --------------------------------------- */
  return (
    <div className="card space-y-4">
      <h3 className="text-xl font-semibold text-primary mb-2">
        Recordings
      </h3>

      {/* Download links */}
      <div>
        <h4 className="font-medium mb-2">Download Links:</h4>
        <ul className="list-disc pl-6 space-y-1">
          {recs.map((r, idx) => (
            <li key={idx}>
              <a
                href={r.stream_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-secondary underline"
              >
                {new Date(r.recording_start).toLocaleString()} (
                {r.file_type})
              </a>
            </li>
          ))}
        </ul>
      </div>

      {/* Stream players */}
      <div className="space-y-4">
        <h4 className="font-medium">Stream Players:</h4>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {recs.map((r, idx) => {
            const ext = r.file_type.toLowerCase();
            const playerKey = keyFor(r, idx, "player-");

            /* Video */
            if (ext === "mp4") {
              return (
                <div key={playerKey} className="space-y-2">
                  <p className="text-sm text-gray-600">
                    {new Date(r.recording_start).toLocaleString()} — Video
                  </p>
                  <video
                    preload="metadata"
                    controls
                    className="w-full rounded shadow"
                    crossOrigin="anonymous"
                    src={r.stream_url + "&rscd=inline&rsct=video/mp4"}
                  >
                    Sorry, your browser doesn’t support HTML5 video.
                  </video>
                </div>
              );
            }

            /* Audio */
            if (["m4a", "mp3", "wav"].includes(ext)) {
              // m4a → audio/mp4
              const mime = ext === "m4a" ? "audio/mp4" : `audio/${ext}`;
              return (
                <div key={playerKey} className="space-y-2">
                  <p className="text-sm text-gray-600">
                    {new Date(r.recording_start).toLocaleString()} — Audio
                  </p>
                  <audio
                    preload="metadata"
                    controls
                    className="w-full"
                    crossOrigin="anonymous"
                    src={r.stream_url}
                  >
                    <source src={r.stream_url} type={mime} />
                    Sorry, your browser doesn’t support HTML5 audio.
                  </audio>
                </div>
              );
            }

            /* Fallback */
            return (
              <div key={playerKey} className="space-y-2">
                <p className="text-sm text-gray-600">
                  {new Date(r.recording_start).toLocaleString()} —{" "}
                  {r.file_type}
                </p>
                <a
                  href={r.stream_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-block px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
                >
                  Download {r.file_type}
                </a>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
