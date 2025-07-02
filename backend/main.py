from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import init_db
from .controllers import sessions, participants, meetings, recordings
from apscheduler.schedulers.asyncio import AsyncIOScheduler

app = FastAPI(title="Zoom Live-Class Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    init_db()
    app.state.scheduler = AsyncIOScheduler()
    app.state.scheduler.start()

@app.on_event("shutdown")
async def shutdown():
    app.state.scheduler.shutdown()


app.include_router(sessions.router)
app.include_router(participants.router)
app.include_router(meetings.router)
app.include_router(recordings.router)
