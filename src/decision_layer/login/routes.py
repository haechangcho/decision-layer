"""Browser login, logout and access-token pages (ADR-130).

These pages are deliberately plain server-rendered HTML: the packaged console stays
unchanged apart from redirecting to /auth/login when the API reports LOGIN_REQUIRED.
"""
from __future__ import annotations

from html import escape
from datetime import datetime, timezone

from urllib.parse import parse_qs

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from ..i18n import _
from . import Login
from .oidc import LoginFailed, groups, new_secret
from .sessions import FLOW_COOKIE, FLOW_SECONDS, SESSION_COOKIE, Person, read_flow, safe_next, sign_flow, sign_session


def _page(title: str, body: str, status: int = 200) -> HTMLResponse:
    return HTMLResponse(status_code=status, headers={"Cache-Control": "no-store"}, content=f"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)} · Decision Layer</title>
<style>
body{{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#f7f8fa;color:#1f2937}}
main{{max-width:720px;margin:48px auto;padding:0 16px}}
h1{{font-size:22px}} p,li{{line-height:1.6}} table{{width:100%;border-collapse:collapse;background:#fff}}
td,th{{padding:8px;border-bottom:1px solid #e5e7eb;text-align:left;font-size:14px}}
code,pre{{background:#111827;color:#f9fafb;border-radius:6px}} code{{padding:2px 6px}}
pre{{padding:12px;overflow-x:auto;white-space:pre-wrap;word-break:break-all}}
input{{padding:8px;border:1px solid #d1d5db;border-radius:6px}}
button,a.button{{padding:8px 14px;border:0;border-radius:6px;background:#111827;color:#fff;text-decoration:none;cursor:pointer}}
</style></head><body><main>{body}</main></body></html>""")


def _date(epoch: int) -> str:
    return datetime.fromtimestamp(epoch, timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def create_router(login: Login) -> APIRouter:
    router = APIRouter(prefix="/auth", include_in_schema=False)
    config = login.config

    def cookie(response: Response, name: str, value: str, max_age: int, path: str = "/") -> None:
        response.set_cookie(name, value, max_age=max_age, path=path, httponly=True,
                            secure=config.secure_cookies, samesite="lax")

    @router.get("/login")
    async def start(next: str | None = None):
        state, nonce, verifier = new_secret(), new_secret(), new_secret()
        try:
            url = await login.oidc.authorize_url(state=state, nonce=nonce, verifier=verifier)
        except LoginFailed as exc:
            return _page(_("Sign-in unavailable"), f"<h1>{escape(_('Sign-in unavailable'))}</h1><p>{escape(exc.message)}</p>", 503)
        response = RedirectResponse(url, status_code=302)
        cookie(response, FLOW_COOKIE, sign_flow(config.session_secret, state=state, nonce=nonce,
                                                verifier=verifier, next_path=safe_next(next)),
               FLOW_SECONDS, path="/auth")
        return response

    @router.get("/callback")
    async def callback(request: Request, code: str | None = None, state: str | None = None):
        flow = read_flow(config.session_secret, request.cookies.get(FLOW_COOKIE))
        retry = f'<p><a class="button" href="/auth/login">{escape(_("Sign in again"))}</a></p>'
        if not flow or not code or not state or state != flow["state"]:
            return _page(_("Sign-in failed"), f"<h1>{escape(_('Sign-in failed'))}</h1><p>{escape(_('The sign-in request expired or did not start in this browser.'))}</p>{retry}", 400)
        try:
            claims = await login.oidc.exchange(code=code, verifier=flow["verifier"], nonce=flow["nonce"])
        except LoginFailed as exc:
            return _page(_("Sign-in failed"), f"<h1>{escape(_('Sign-in failed'))}</h1><p>{escape(exc.message)}</p>{retry}", 401)
        role = login.role(groups(claims, config.groups_claim))
        if role is None:
            return _page(_("Access denied"), f"<h1>{escape(_('Access denied'))}</h1><p>{escape(_('Your account is not in a group allowed to use Decision Layer.'))}</p>", 403)
        name = claims.get("name") or claims.get("preferred_username") or claims.get("email")
        person = Person(subject=f"oidc:{claims['sub']}", role=role, name=str(name) if name else None)
        response = RedirectResponse(safe_next(flow.get("next")), status_code=302)
        cookie(response, SESSION_COOKIE, sign_session(config.session_secret, person, config.session_hours),
               int(config.session_hours * 3600))
        response.delete_cookie(FLOW_COOKIE, path="/auth")
        return response

    @router.get("/logout")
    async def logout():
        response = RedirectResponse(await login.oidc.logout_url() or "/auth/logged-out", status_code=302)
        response.delete_cookie(SESSION_COOKIE, path="/")
        return response

    @router.get("/logged-out")
    async def logged_out():
        return _page(_("Signed out"), f'<h1>{escape(_("Signed out"))}</h1><p><a class="button" href="/auth/login">{escape(_("Sign in"))}</a></p>')

    def tokens_page(person: Person, records, created: str | None = None) -> HTMLResponse:
        rows = "".join(
            f"<tr><td>{escape(r.label)}</td><td>{_date(r.created_at)}</td><td>{_date(r.expires_at)}</td>"
            f"<td>{escape(_('Active') if r.active else _('Revoked') if r.revoked_at else _('Expired'))}</td><td>"
            + (f'<form method="post" action="/auth/tokens/{escape(r.id)}/revoke"><button>{escape(_("Revoke"))}</button></form>' if r.active else "")
            + "</td></tr>" for r in records)
        shown = ""
        if created:
            mcp_url = f"{config.public_url}/mcp"
            shown = (f"<h2>{escape(_('New access token'))}</h2><p>{escape(_('Copy it now. It is shown only once.'))}</p>"
                     f"<pre>{escape(created)}</pre><p>Claude Code:</p>"
                     f"<pre>claude mcp add --transport http decision-layer {escape(mcp_url)} --header \"Authorization: Bearer {escape(created)}\"</pre>"
                     f"<p>Codex (~/.codex/config.toml):</p><pre>[mcp_servers.decision-layer]\nurl = \"{escape(mcp_url)}\"\n"
                     f"http_headers = {{ Authorization = \"Bearer {escape(created)}\" }}</pre>")
        who = escape(person.name or person.subject)
        body = (f"<h1>{escape(_('Access tokens'))}</h1><p>{who} · {escape(person.role)} · "
                f'<a href="/ui/">{escape(_("Open console"))}</a> · <a href="/auth/logout">{escape(_("Sign out"))}</a></p>'
                f"<p>{escape(_('Tokens let MCP and REST clients act as you. They keep your current role until they expire or you revoke them.'))}</p>"
                f"{shown}<form method=\"post\" action=\"/auth/tokens\"><input name=\"label\" maxlength=\"80\" placeholder=\"{escape(_('Label, e.g. Claude Code'))}\"> "
                f"<button>{escape(_('Create token'))}</button></form><h2>{escape(_('Your tokens'))}</h2>"
                f"<table><tr><th>{escape(_('Label'))}</th><th>{escape(_('Created'))}</th><th>{escape(_('Expires'))}</th><th>{escape(_('Status'))}</th><th></th></tr>{rows}</table>")
        return _page(_("Access tokens"), body)

    def require_session(request: Request) -> Person | RedirectResponse:
        # Tokens are created only from a browser session, never by another token.
        person = login.session_person(request)
        return person or RedirectResponse("/auth/login?next=/auth/tokens", status_code=302)

    @router.get("/tokens")
    async def list_tokens(request: Request):
        person = require_session(request)
        if isinstance(person, RedirectResponse):
            return person
        return tokens_page(person, await login.tokens.list(person.subject))

    @router.post("/tokens")
    async def create_token(request: Request):
        person = require_session(request)
        if isinstance(person, RedirectResponse):
            return person
        label = parse_qs((await request.body())[:2048].decode(errors="replace")).get("label", [""])[0]
        token, _record = await login.tokens.create(person, label, config.access_token_days)
        return tokens_page(person, await login.tokens.list(person.subject), created=token)

    @router.post("/tokens/{token_id}/revoke")
    async def revoke_token(request: Request, token_id: str):
        person = require_session(request)
        if isinstance(person, RedirectResponse):
            return person
        await login.tokens.revoke(person.subject, token_id)
        return RedirectResponse("/auth/tokens", status_code=303)

    return router
