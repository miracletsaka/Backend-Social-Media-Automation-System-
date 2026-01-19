from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers.generation import router as generation_router
from app.routers import brands
from app.routers.topics import router as topics_router
from app.routers.content import router as content_router
from app.routers.approvals import router as approvals_router
from app.routers import platforms
from app.routers import stats
from app.routers import schedule
from app.routers import publisher
from app.routers import export
from app.routers import publishing
from app.routers import make_bridge
from app.routers import media
from app.routers import generation_image
from app.routers import brand_profiles
from app.routers.auth import router as auth_router
from app.routers import admin_users
# Create FastAPI app FIRST
app = FastAPI(title="AI Marketing System")
# Enable CORS (required for Next.js frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://us2.make.com/",
        "https://app.neuroflowai.co.uk/",
        "https://neuroflowai.co.uk/",
        "https://api.neuroflowai.co.uk/",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Register routers
app.include_router(topics_router)
app.include_router(content_router)
app.include_router(approvals_router)
app.include_router(generation_router)
app.include_router(brands.router)
app.include_router(platforms.router)
app.include_router(stats.router)
app.include_router(schedule.router)
app.include_router(publisher.router)
app.include_router(export.router)
app.include_router(publishing.router)
app.include_router(make_bridge.router)
app.include_router(media.router)
app.include_router(generation_image.router)
app.include_router(brand_profiles.router)
app.include_router(auth_router)
app.include_router(admin_users.router)

# Health check
@app.get("/")
def health_check():
    return {"status": "ok"}
