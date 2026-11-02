"""Serve the packaged console and canonical API on one local origin."""
from contextlib import asynccontextmanager
from pathlib import Path

from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.responses import RedirectResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from .api.app import create_app
from .project import Project
from .settings import Settings

STATIC_DIR = Path(__file__).parent / "static"


class ConsoleFiles(StaticFiles):
    async def get_response(self, path, scope):
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            # Browser routes can contain arbitrary Method names; missing assets
            # must remain 404 rather than receiving HTML with a script MIME type.
            if exc.status_code != 404 or path.startswith("assets/"):
                raise
            return await super().get_response("index.html", scope)


def create_console(settings=None, static_dir=None):
    settings = settings or Settings()
    directory = Path(static_dir or STATIC_DIR)
    if not (directory / "index.html").is_file():
        raise RuntimeError("Admin UI is missing. Install the released package, or run npm run build:console in web/.")
    api = create_app(settings)
    project = Project.find(settings.project_dir, required=bool(settings.project_dir))

    @api.get("/project")
    async def project_info():
        return {"name": project.config.name if project else "Decision Layer", "path": str(project.root) if project else ""}

    async def home(request):
        return RedirectResponse("/ui/")

    routes = [Route("/", home)]
    lifespan = api.router.lifespan_context
    if settings.shared:
        # Remote MCP calls back into this API with the caller's own token (ADR-130).
        from .mcp.remote import PATH, remote_app
        from .login.oauth import oauth_routes

        mcp_app, mcp_lifespan = remote_app(settings, api.state.login)
        routes.extend(oauth_routes(api.state.login))
        routes.append(Route(PATH, endpoint=mcp_app, methods=["GET", "POST", "DELETE"]))

        @asynccontextmanager
        async def lifespan(app):
            async with api.router.lifespan_context(app), mcp_lifespan(app):
                yield

    # API middleware still enforces the same Host, Origin and caller checks.
    console = Starlette(routes=[
        *routes,
        Mount("/api", app=api),
        Mount("/ui", app=ConsoleFiles(directory=directory, html=True)),
        Mount("/", app=api),
    ], lifespan=lifespan)
    if settings.shared:
        from starlette.middleware.trustedhost import TrustedHostMiddleware
        console.add_middleware(TrustedHostMiddleware, allowed_hosts=list(settings.http_allowed_hosts))
    return console
