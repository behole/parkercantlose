from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader
from starlette.responses import HTMLResponse

from parker.config import get_settings
from parker.db import get_engine, init_db
from parker.web.public_routes import router as public_router
from parker.web.routes import router

WEB_DIR = Path(__file__).parent


class Templates:
    def __init__(self, directory: Path):
        self.env = Environment(loader=FileSystemLoader(str(directory)))

    def template_response(self, name: str, context: dict) -> HTMLResponse:
        template = self.env.get_template(name)
        html = template.render(**context)
        return HTMLResponse(content=html)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Parker Debate Review")

    app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")

    engine = get_engine(settings.db_path)
    init_db(engine)
    app.state.engine = engine
    app.state.templates = Templates(directory=WEB_DIR / "templates")

    app.include_router(public_router)
    app.include_router(router, prefix="/admin")
    return app
