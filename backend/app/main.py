from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.routes import router as api_v1_router
from app.api.v1.analysis_routes import router as analysis_router
from app.api.v1.dashboard_routes import router as dashboard_router
from app.api.v1.hermes_agent_routes import router as hermes_agent_router
from app.core.config import allowed_origins, settings
from app.db import Base, SessionLocal, engine
from app.db.migrations import run_migrations
from app.db.seed import seed_reference_data


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        run_migrations(db)
        seed_reference_data(db)
    yield


app = FastAPI(
    title="Business Dashboard API",
    version="0.1.0",
    description="企业 AI 经营驾驶舱 MVP API",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_v1_router)
app.include_router(analysis_router)
app.include_router(dashboard_router)
app.include_router(hermes_agent_router)


@app.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}
