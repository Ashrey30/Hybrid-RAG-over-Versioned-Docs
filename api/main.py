"""FastAPI app: account authentication, role-protected document Q&A, and static frontend."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr

from api.auth import SESSION_TTL_SECONDS, AuthStore, User
from api.pipeline import RagPipeline

app = FastAPI(title="Hybrid RAG")
_pipe: RagPipeline | None = None
_auth_store = AuthStore()
SESSION_COOKIE = "hybrid_rag_session"


def pipe() -> RagPipeline:
    global _pipe
    if _pipe is None:
        _pipe = RagPipeline()
    return _pipe


class AskRequest(BaseModel):
    question: str


class Credentials(BaseModel):
    email: EmailStr
    password: str


def current_user(request: Request) -> User:
    user = _auth_store.user_for_session(request.cookies.get(SESSION_COOKIE))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Please sign in.")
    return user


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        secure=os.getenv("AUTH_COOKIE_SECURE", "").casefold() in {"1", "true", "yes"},
        samesite="lax",
        path="/",
    )


def user_payload(user: User) -> dict:
    return {"email": user.email, "role": user.role, "access_group": user.access_group}


@app.on_event("startup")
def warm() -> None:
    pipe()


@app.get("/health")
def health():
    return {"ok": True}


@app.middleware("http")
async def no_cache_ui(request, call_next):
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.endswith((".html", ".css", ".js", ".svg")):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    return response


@app.post("/auth/register", status_code=status.HTTP_201_CREATED)
def register(credentials: Credentials, response: Response):
    try:
        user = _auth_store.create_user(credentials.email, credentials.password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except sqlite3.IntegrityError as exc:
        if "users.email" in str(exc):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with that email already exists.",
            ) from exc
        raise
    set_session_cookie(response, _auth_store.create_session(user.id))
    return user_payload(user)


@app.post("/auth/login")
def login(credentials: Credentials, response: Response):
    user = _auth_store.authenticate(credentials.email, credentials.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Email or password is incorrect.")
    set_session_cookie(response, _auth_store.create_session(user.id))
    return user_payload(user)


@app.get("/auth/me")
def me(user: User = Depends(current_user)):
    return user_payload(user)


@app.post("/auth/logout")
def logout(request: Request, response: Response, user: User = Depends(current_user)):
    _auth_store.revoke_session(request.cookies.get(SESSION_COOKIE))
    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        secure=os.getenv("AUTH_COOKIE_SECURE", "").casefold() in {"1", "true", "yes"},
        httponly=True,
        samesite="lax",
    )
    return {"ok": True}


@app.get("/suggestions")
def suggestions(exclude: list[str] = Query(default=[]), user: User = Depends(current_user)):
    return {"suggestions": pipe().suggestions(user.access_group, exclude=exclude)}


@app.post("/ask")
def ask(req: AskRequest, user: User = Depends(current_user)):
    question = req.question.strip()
    if not question:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Question cannot be empty.")
    resp = pipe().ask(question, user.access_group)
    dbg = resp.pop("_debug", None)
    if user.role == "admin" and os.getenv("RAG_DEBUG") == "1":
        resp["_debug"] = dbg
    if user.role != "admin":
        resp.pop("trace", None)
    return resp


app.mount("/", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="static")
