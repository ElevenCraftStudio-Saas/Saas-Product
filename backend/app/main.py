from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import engine, Base
from .routers import auth, events, photos, match, guest
import os
import logging

from fastapi.staticfiles import StaticFiles

# Make application loggers (wedfind.*) visible — uvicorn only configures its own
# loggers, so without this our S3/upload/audit logs are silently dropped.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logging.getLogger("wedfind").setLevel(logging.INFO)

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="WedFind AI API")

# Mount static files
app.mount("/uploads", StaticFiles(directory=os.getenv("UPLOAD_DIR", "../uploads")), name="uploads")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_URL", "http://localhost:3000")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(events.router, prefix="/api/events", tags=["Events"])
app.include_router(photos.router, prefix="/api/photos", tags=["Photos"])
app.include_router(match.router, prefix="/api/match", tags=["Matching"])
app.include_router(guest.router, prefix="/api/guest", tags=["Guest"])

@app.get("/")
def read_root():
    return {"message": "Welcome to WedFind AI API"}
