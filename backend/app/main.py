from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.config import settings

app = FastAPI(
    title=settings.app_name,
    description="Accessible event history and acknowledgement API",
    version="1.0.0",
)

cors_origins_list = [
    origin.strip()
    for origin in settings.cors_origins.split(",")
    if origin.strip()
]

# Avoid wildcard origins when credentials are enabled
effective_allow_credentials = settings.cors_allow_credentials
if "*" in cors_origins_list and effective_allow_credentials:
    effective_allow_credentials = False

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins_list,
    allow_origin_regex=r"^https://.*\.vercel\.app$",
    allow_credentials=effective_allow_credentials,
    allow_methods=["GET", "POST", "PUT", "OPTIONS", "HEAD"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_prefix)