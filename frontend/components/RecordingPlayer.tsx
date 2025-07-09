"use client";
import { useEffect, useState } from "react";
import { fetchRecordingInfo } from "../lib/api";

export function RecordingPlayer({ sessionId, fileId }: { sessionId: string; fileId: string }) {
  const [url, setUrl] = useState<string | null>(null);

  useEffect(() => {
    fetchRecordingInfo(sessionId, fileId)
      .then(info => setUrl(info.stream_url))
      .catch(console.error);
  }, [sessionId, fileId]);

  if (!url) return <p>Loading …</p>;

  return (
    <video controls className="w-full">
      <source src={url} type="video/mp4" />
      Your browser doesn’t support HTML5 video.
    </video>
  );
}