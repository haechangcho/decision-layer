"""HTTP boundary policies, separate from application lifecycle and resources."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from ..core.errors import DecisionLayerError
from ..i18n import negotiate, set_locale
from ..settings import Settings


def install_http_handlers(app: FastAPI, settings: Settings) -> None:
    @app.middleware("http")
    async def locale(request: Request, call_next):
        from urllib.parse import urlsplit

        try:
            host = urlsplit("//" + request.headers.get("host", "")).hostname
            origin = request.headers.get("origin")
            parsed_origin = urlsplit(origin) if origin else None
        except ValueError:
            return JSONResponse(
                status_code=403, content={"error": {"code": "LOCAL_HTTP_ORIGIN_DENIED"}}
            )
        if host not in settings.http_allowed_hosts or (
            parsed_origin
            and (
                parsed_origin.scheme not in ("http", "https")
                or parsed_origin.hostname not in settings.http_allowed_hosts
            )
        ):
            return JSONResponse(
                status_code=403,
                content={
                    "error": {
                        "code": "LOCAL_HTTP_ORIGIN_DENIED",
                        "message": "Host or Origin is not allowed for this local deployment.",
                    }
                },
            )
        set_locale(negotiate(request.headers.get("accept-language"), settings.locale))
        response = await call_next(request)
        response.headers["Content-Language"] = negotiate(
            request.headers.get("accept-language"), settings.locale
        )
        return response

    @app.exception_handler(DecisionLayerError)
    async def _app_error(_request: Request, exc: DecisionLayerError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.http_status, content={"error": exc.to_dict()}
        )
