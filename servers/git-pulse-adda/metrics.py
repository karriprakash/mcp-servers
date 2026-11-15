"""GitHub developer-metrics logic for the Git Pulse Adda MCP server.

Kept free of MCP and HTTP-library imports so it can be unit-tested with a fake client.
`client` is any object with `async get(url, headers=...)` returning something with
`status_code`, `json()` and `text` (an `httpx.AsyncClient` fits).
"""
from __future__ import annotations

import asyncio
import os
import re

GITHUB_API = "https://api.github.com"
# GitHub usernames: 1-39 chars, alphanumeric or single hyphens, no leading/trailing hyphen.
_USERNAME_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}$")


def valid_username(username: str) -> bool:
    return bool(_USERNAME_RE.match(username or ""))


def _headers(token: str) -> dict:
    headers = {"Accept": "application/vnd.github.v3+json"}
    effective = token or os.getenv("GITHUB_TOKEN", "")
    if effective:
        headers["Authorization"] = f"Bearer {effective}"
    return headers


def _github_message(resp) -> str:
    try:
        body = resp.json()
        if isinstance(body, dict) and body.get("message"):
            return str(body["message"])
    except Exception:
        pass
    return (resp.text or "")[:200]


async def fetch_metrics(username: str, client, token: str = "") -> dict:
    if not valid_username(username):
        return {"error": "Invalid GitHub username."}

    headers = _headers(token)
    user_resp, repos_resp = await asyncio.gather(
        client.get(f"{GITHUB_API}/users/{username}", headers=headers),
        client.get(f"{GITHUB_API}/users/{username}/repos?sort=updated&per_page=30", headers=headers),
    )

    if user_resp.status_code != 200:
        return {"error": f"Failed to fetch user profile ({user_resp.status_code}): {_github_message(user_resp)}"}

    user_data = user_resp.json()
    warning = None
    repos_data: list = []
    if repos_resp.status_code == 200:
        body = repos_resp.json()
        repos_data = body if isinstance(body, list) else []
    else:
        warning = f"Could not fetch repositories ({repos_resp.status_code}): {_github_message(repos_resp)}"

    top_repos = []
    language_counts: dict[str, int] = {}
    for r in repos_data:
        if isinstance(r, dict) and not r.get("fork"):
            lang = r.get("language")
            if lang:
                language_counts[lang] = language_counts.get(lang, 0) + 1
            top_repos.append({
                "name": r.get("name"),
                "stars": r.get("stargazers_count", 0),
                "forks": r.get("forks_count", 0),
                "language": lang,
                "description": r.get("description"),
                "url": r.get("html_url"),
            })

    top_repos.sort(key=lambda x: x["stars"], reverse=True)

    result = {
        "name": user_data.get("name") or username,
        "username": username,
        "bio": user_data.get("bio"),
        "avatar_url": user_data.get("avatar_url"),
        "public_repos": user_data.get("public_repos"),
        "followers": user_data.get("followers"),
        "following": user_data.get("following"),
        "language_breakdown": language_counts,
        "top_repositories": top_repos[:6],
    }
    if warning:
        result["warning"] = warning
    return result
