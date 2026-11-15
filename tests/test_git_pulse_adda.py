import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "servers" / "git-pulse-adda"))

from metrics import fetch_metrics, valid_username  # noqa: E402


class FakeResp:
    def __init__(self, status, body=None, text=""):
        self.status_code, self._body, self.text = status, body, text

    def json(self):
        if self._body is None:
            raise ValueError("no json")
        return self._body


class FakeClient:
    def __init__(self, user, repos):
        self.user, self.repos, self.calls = user, repos, []

    async def get(self, url, headers=None):
        self.calls.append((url, headers))
        return self.repos if "/repos" in url else self.user


def run(coro):
    return asyncio.run(coro)


REPOS = [
    {"name": "a", "stargazers_count": 3, "forks_count": 1, "language": "Python", "description": "x", "html_url": "u1"},
    {"name": "b", "stargazers_count": 9, "forks_count": 0, "language": "Java", "description": None, "html_url": "u2"},
    {"name": "c", "stargazers_count": 50, "forks_count": 0, "language": "Python", "fork": True, "html_url": "u3"},
    {"name": "d", "stargazers_count": 1, "language": "Python", "html_url": "u4"},
]


def test_happy_path_sorted_and_forks_excluded():
    c = FakeClient(FakeResp(200, {"name": None, "bio": "hi", "public_repos": 4, "followers": 2, "following": 1}),
                   FakeResp(200, REPOS))
    out = run(fetch_metrics("karriprakash", c))
    assert out["name"] == "karriprakash"  # falls back to username
    assert [r["name"] for r in out["top_repositories"]] == ["b", "a", "d"]
    assert out["language_breakdown"] == {"Python": 2, "Java": 1}
    assert "warning" not in out


def test_top_repositories_capped_at_six():
    repos = [{"name": str(i), "stargazers_count": i, "language": "Go"} for i in range(20)]
    out = run(fetch_metrics("u", FakeClient(FakeResp(200, {}), FakeResp(200, repos))))
    assert len(out["top_repositories"]) == 6 and out["top_repositories"][0]["name"] == "19"


def test_user_not_found_returns_error():
    out = run(fetch_metrics("ghost", FakeClient(FakeResp(404, {"message": "Not Found"}), FakeResp(404, {}))))
    assert "404" in out["error"] and "Not Found" in out["error"]


def test_repo_failure_keeps_profile_with_warning():
    out = run(fetch_metrics("u", FakeClient(FakeResp(200, {"name": "N"}), FakeResp(403, {"message": "rate limited"}))))
    assert out["name"] == "N" and out["top_repositories"] == [] and "rate limited" in out["warning"]


@pytest.mark.parametrize("bad", ["", "a b", "../x", "a/b", "-a", "a-", "a--b", "x" * 40, "a?b=1"])
def test_invalid_usernames_never_reach_the_network(bad):
    c = FakeClient(FakeResp(200, {}), FakeResp(200, []))
    assert run(fetch_metrics(bad, c)) == {"error": "Invalid GitHub username."}
    assert c.calls == []


@pytest.mark.parametrize("good", ["a", "karriprakash", "a-b-c", "A1", "x" * 39])
def test_valid_usernames(good):
    assert valid_username(good)


def test_token_from_argument_then_environment(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "env-token")
    c = FakeClient(FakeResp(200, {}), FakeResp(200, []))
    run(fetch_metrics("u", c))
    assert c.calls[0][1]["Authorization"] == "Bearer env-token"
    c = FakeClient(FakeResp(200, {}), FakeResp(200, []))
    run(fetch_metrics("u", c, token="arg-token"))
    assert c.calls[0][1]["Authorization"] == "Bearer arg-token"
    monkeypatch.delenv("GITHUB_TOKEN")
    c = FakeClient(FakeResp(200, {}), FakeResp(200, []))
    run(fetch_metrics("u", c))
    assert "Authorization" not in c.calls[0][1]
