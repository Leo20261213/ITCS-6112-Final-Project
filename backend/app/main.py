import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .ai.service import ensure_settings
from .database import Base, SessionLocal, engine
from .routers import admin, ai, analytics, attachments, auth, conversation, notifications, tickets
from .seed import seed


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        if os.getenv("SEED_DEMO_DATA", "1") == "1":
            seed(db)
        ensure_settings(db)  # US-21: settings row exists before any request reads it
    yield


app = FastAPI(title="Neural Support Solutions Help Desk", version="0.3.0 (Sprint 3)", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(tickets.router)
app.include_router(conversation.router)
app.include_router(attachments.router)
app.include_router(notifications.router)
app.include_router(ai.router)
app.include_router(analytics.router)
app.include_router(admin.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
