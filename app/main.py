import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.routers import ui, api

APP_DIR = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    from surya.pipeline import TableExtractionPipeline

    app.state.pipeline = TableExtractionPipeline()
    yield
    del app.state.pipeline


app = FastAPI(title="Pardarshi", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")

templates = Jinja2Templates(directory=APP_DIR / "templates")

app.include_router(ui.router)
app.include_router(api.router, prefix="/api")
