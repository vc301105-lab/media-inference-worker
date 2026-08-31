"""YouTube publish — upload the finished film with OAuth (Google API).

Setup:
    pip install google-api-python-client google-auth-oauthlib google-auth-httplib2
    # Get OAuth client credentials from Google Cloud Console (Desktop app type)
    # save as: <repo>/youtube_client_secret.json  or set YOUTUBE_CLIENT_SECRET

The first upload opens a browser for consent; the token is cached in the film
folder so subsequent uploads are silent.
"""

from __future__ import annotations

import os
from pathlib import Path

from .config import REPO_ROOT, load_env

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
TOKEN_NAME = "youtube_token.json"


def _secrets_path() -> Path:
    env = os.environ.get("YOUTUBE_CLIENT_SECRET")
    if env:
        p = Path(env)
        if p.exists():
            return p
    return REPO_ROOT / "youtube_client_secret.json"


def _creds(project, secrets: Path):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    token_file = project.root / TOKEN_NAME
    creds = None
    if token_file.exists():
        creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(secrets), SCOPES)
            creds = flow.run_local_server(port=0, open_browser=False)
        token_file.write_text(creds.to_json())
    return creds


def upload_film(project, movie: Path, title: str | None = None, description: str = "", tags: list[str] | None = None, privacy: str = "public", category_id: str = "24") -> str:
    """Upload movie to YouTube. Returns the video URL."""
    load_env()
    secrets = _secrets_path()
    if not secrets.exists():
        raise FileNotFoundError(
            "YouTube setup missing: google_client_secret par `youtube_client_secret.json` rakhna hoga "
            "(Google Cloud Console → OAuth Desktop app). Dekho README → YouTube section."
        )
    if not movie.exists():
        raise FileNotFoundError(f"Movie not found: {movie} — pehle render chalao.")

    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    creds = _creds(project, secrets)
    youtube = build("youtube", "v3", credentials=creds)

    body = {
        "snippet": {
            "title": title or project.film.title,
            "description": description or (
                f"{project.film.logline}\n\nGenerated with AI Film Studio.\n"
                f"Genre: {project.film.genre} · ~{project.film.duration:.0f}s"
            ),
            "tags": tags or ["AI film", project.film.genre, "short film"],
            "categoryId": category_id,
        },
        "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False},
    }
    media = MediaFileUpload(str(movie), chunksize=-1, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"   Uploading… {int(status.progress() * 100)}%", flush=True)
    video_id = response["id"]
    return f"https://youtu.be/{video_id}"
