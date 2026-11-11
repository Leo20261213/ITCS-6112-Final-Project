import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, SessionLocal, engine
from .routers import admin, ai, auth, collaboration, tickets
from .seed import seed


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    if os.getenv("SEED_DEMO_DATA", "1") == "1":
        with SessionLocal() as db:
            seed(db)
    yield


app = FastAPI(
    title="Neural Support Solutions Help Desk",
    version="1.0.0",
    description="Help desk API with ticket workflows, collaboration, and AI assistance.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(tickets.router)
app.include_router(admin.router)
app.include_router(collaboration.router)
app.include_router(ai.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
