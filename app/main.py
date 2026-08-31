from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database.db import init_db, seed_data

from app.routes import auth, tenders, bids, documents, verification, compliance, risk, officer, audit

import os

app = FastAPI(title="BidSetu API", version="1.0.0")

allowed_origins_env = os.getenv("CORS_ORIGINS", "")
allowed_origins = [o.strip() for o in allowed_origins_env.split(",") if o.strip()]
if not allowed_origins:
    allowed_origins = ["http://localhost:3000", "http://127.0.0.1:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"https://.*\.netlify\.app|https://.*\.onrender\.com|https://.*\.vercel\.app|http://localhost:\d+|http://127\.0\.0\.1:\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    init_db()
    seed_data()

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(tenders.router, prefix="/tenders", tags=["tenders"])
app.include_router(bids.router, prefix="/bids", tags=["bids"])
app.include_router(documents.router, prefix="/documents", tags=["documents"])
app.include_router(verification.router, prefix="/verification", tags=["verification"])
app.include_router(compliance.router, prefix="/compliance", tags=["compliance"])
app.include_router(risk.router, prefix="/risk", tags=["risk"])
app.include_router(officer.router, prefix="/officer", tags=["officer"])
app.include_router(audit.router, prefix="/audit", tags=["audit"])

@app.get("/")
def read_root():
    return {"message": "BidSetu API", "version": "1.0.0"}
