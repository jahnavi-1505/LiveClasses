from datetime import datetime, timedelta

def build_placeholder_ics(session_id: str, title: str, description: str):
    now_dt = datetime.utcnow()
    uid = f"{session_id}@live-classes"
    return (
        "BEGIN:VCALENDAR\n"
        "VERSION:2.0\n"
        "PRODID:-//Live Classes//EN\n"
        "METHOD:REQUEST\n"
        "BEGIN:VEVENT\n"
        f"UID:{uid}\n"
        f"DTSTAMP:{now_dt.strftime('%Y%m%dT%H%M%SZ')}\n"
        f"DTSTART:{now_dt.strftime('%Y%m%dT%H%M%SZ')}\n"
        f"DTEND:{(now_dt + timedelta(hours=1)).strftime('%Y%m%dT%H%M%SZ')}\n"
        f"SUMMARY:{title} (not yet scheduled)\n"
        "END:VEVENT\n"
        "END:VCALENDAR"
    )


def build_meeting_ics(meeting_id: str, title: str, description: str, join_url: str, start: datetime):
    dtstamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    dtstart = start.strftime("%Y%m%dT%H%M%SZ")
    dtend = (start + timedelta(hours=1)).strftime("%Y%m%dT%H%M%SZ")
    uid = f"{meeting_id}@live-classes"
    return (
        "BEGIN:VCALENDAR\n"
        "VERSION:2.0\n"
        "PRODID:-//Live Classes//EN\n"
        "METHOD:REQUEST\n"
        "BEGIN:VEVENT\n"
        f"UID:{uid}\n"
        f"DTSTAMP:{dtstamp}\n"
        f"DTSTART:{dtstart}\n"
        f"DTEND:{dtend}\n"
        f"SUMMARY:{title}\n"
        f"DESCRIPTION:Join Zoom Meeting: {join_url}\n\n{description}\n"
        f"LOCATION:{join_url}\n"
        "END:VEVENT\n"
        "END:VCALENDAR"
    )