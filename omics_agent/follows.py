"""Following researchers (F5): who a person page's name is, by ORCID, and the /follows/people routes.

A person page searches Europe PMC by surname and initials, which mixes people who share a name. Following keys on
ORCID only (DECISIONS D7, after papertok's unverified-identity guard):

- `identity(name)` reads the name's newest papers with their author lists and counts the ORCIDs Europe PMC tags on the
  matching author. It names an ORCID only when one ORCID accounts for most of the ORCID-tagged papers; when several
  share the tagged papers it says the name matches several people, and when none is tagged it says so. The person
  page offers Follow only for the first case.
- What a followed person brings is the datasets locus holds that their ORCID-linked papers deposited or cite
  (Europe PMC `AUTHORID:"<orcid>"`, never the name query), newest paper first, each marked new until the account marks
  it seen. Europe PMC links only part of a person's papers to their ORCID (29 Oct: 5 of 42 for Carson Thoreen), and the
  pages say so.

Bounds: 200 follows an account; one /updates call reads at most 40 of them (newest follows first), 4 at a time, within
45 seconds overall, and keeps each ORCID's answer for 6 hours. Every upstream call goes through pace.py (Europe PMC at
most 5 a second, ORCID at most 2 a second, app-wide). Sessions, the CSRF guard and the error shape come from users.py.
"""

import json
import re
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, wait

import httpx
from fastapi import APIRouter, Depends, FastAPI, Query, Response
from pydantic import BaseModel, Field, field_validator

from . import pace, person, users
from .saved import ACCESSION
from .users import ApiError, Db, User, iso

router = APIRouter(prefix="/follows/people", tags=["follows"], dependencies=[Depends(users.require_intent)])
public = APIRouter(tags=["follows"])

MAX_FOLLOWS = 200
FETCH_MAX = 40
FETCH_WORKERS = 4
FETCH_SECONDS = 45.0
CACHE_SECONDS = 6 * 3600
NAME_MAX = 200
SEEN_MAX = 500
PAGE = 100
LIMITS = {"follows": MAX_FOLLOWS, "checked": FETCH_MAX, "seen": SEEN_MAX}
ORCID_ID = re.compile(r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$")


def valid_orcid(value: str) -> bool:
    """The ORCID form and its ISO 7064 11,2 check digit."""
    if not ORCID_ID.match(value):
        return False
    total = 0
    for ch in value.replace("-", "")[:-1]:
        total = (total + int(ch)) * 2
    check = (12 - total % 11) % 11
    return value[-1] == ("X" if check == 10 else str(check))


# ---------------------------------------------------------------- caches


class Cache:
    """Answers kept for CACHE_SECONDS, per key. Failures are never kept."""

    def __init__(self, seconds: float = CACHE_SECONDS, size: int = 2000):
        self.seconds, self.size = seconds, size
        self.lock = threading.Lock()
        self.items: dict[str, tuple[float, dict]] = {}

    def get(self, key: str) -> dict | None:
        with self.lock:
            hit = self.items.get(key)
            return hit[1] if hit and hit[0] > time.monotonic() - self.seconds else None

    def put(self, key: str, value: dict) -> None:
        with self.lock:
            if len(self.items) >= self.size:
                self.items.pop(next(iter(self.items)))
            self.items[key] = (time.monotonic(), value)

    def clear(self) -> None:
        with self.lock:
            self.items.clear()


IDENTITIES = Cache()
WORK = Cache()


def clear_caches() -> None:
    IDENTITIES.clear()
    WORK.clear()


# ---------------------------------------------------------------- who a name is


def _same_author(author: dict, surname: str, initials: str) -> bool:
    last = person._plain(author.get("lastName") or "")
    mine = (author.get("initials") or "").replace(".", "").replace(" ", "").upper()
    return bool(mine) and last == person._plain(surname) and (mine.startswith(initials) or initials.startswith(mine))


def orcid_name(orcid: str, deadline: float | None = None) -> str | None:
    """The public name on an ORCID record, or None when ORCID does not answer or shows none."""
    try:
        name = pace.orcid_get(f"/{orcid}/person", deadline=deadline).get("name") or {}
    except (httpx.HTTPError, pace.PaceTimeout, ValueError):
        return None
    given, family = (name.get("given-names") or {}).get("value"), (name.get("family-name") or {}).get("value")
    credit = (name.get("credit-name") or {}).get("value")
    return credit or " ".join(p for p in (given, family) if p) or None


def identity(name: str) -> dict:
    """Which ORCID a person page's name stands for, judged from the ORCIDs Europe PMC tags on the matching author of
    the name's newest 100 papers. status: "one" (orcid set), "several", "none" or "no_name". httpx errors pass through."""
    query = person.author_query(name)
    if not query:
        return {"name": name, "status": "no_name"}
    if (hit := IDENTITIES.get(query)) is not None:
        return hit | {"name": name}
    body = pace.epmc_get("/search", {"query": f'AUTH:"{query}"', "format": "json", "resultType": "core", "pageSize": PAGE, "sort": "P_PDATE_D desc"})
    surname, _, initials = query.rpartition(" ")
    counts: Counter[str] = Counter()
    results = body["resultList"]["result"]
    for r in results:
        ids = {(a.get("authorId") or {}).get("value") for a in (r.get("authorList") or {}).get("author", [])
               if (a.get("authorId") or {}).get("type") == "ORCID" and _same_author(a, surname, initials)}
        counts.update(i for i in ids if i and valid_orcid(i))
    tagged = sum(counts.values())
    out = {"name": name, "query": query, "matched": body.get("hitCount", 0), "scanned": len(results), "tagged": tagged, "orcids": len(counts)}
    if not counts:
        out["status"] = "none"
    else:
        top, claimed = counts.most_common(1)[0]
        if claimed * 2 <= tagged:
            out["status"] = "several"
        else:
            linked = pace.epmc_get("/search", {"query": f'AUTHORID:"{top}"', "format": "json", "resultType": "lite", "pageSize": 1})
            out |= {"status": "one", "orcid": top, "claimed": claimed, "linked": linked.get("hitCount", 0), "orcid_name": orcid_name(top)}
    IDENTITIES.put(query, out)
    return out


# ---------------------------------------------------------------- what a followed person brings


def work(orcid: str, deadline: float | None = None) -> dict:
    """The datasets locus holds that the ORCID's Europe PMC papers deposited or cite, newest paper first, from at most
    the newest 100 of those papers. Kept 6 hours per ORCID. httpx errors and PaceTimeout pass through."""
    if (hit := WORK.get(orcid)) is not None:
        return hit
    body = pace.epmc_get("/search", {"query": f'AUTHORID:"{orcid}"', "format": "json", "resultType": "lite", "pageSize": PAGE, "sort": "P_PDATE_D desc"},
                         deadline=deadline)
    papers = [{"key": r["id"], "pmid": r.get("pmid"), "doi": r.get("doi"), "title": (r.get("title") or "").rstrip("."), "year": r.get("pubYear")}
              for r in body["resultList"]["result"]]
    linked = person.datasets_of(papers)
    datasets: list[dict] = []
    for p in papers:
        for d in linked.get(p["key"], []):
            if d["accession"] not in {x["accession"] for x in datasets}:
                datasets.append(d | {"paper": {k: p[k] for k in ("title", "year", "pmid", "doi")}})
    out = {"linked": body.get("hitCount", 0), "read": len(papers), "datasets": datasets}
    WORK.put(orcid, out)
    return out


# ---------------------------------------------------------------- routes


def _orcid(value: str) -> str:
    value = value.strip().removeprefix("https://orcid.org/").removeprefix("http://orcid.org/").upper()
    if not valid_orcid(value):
        raise ValueError("not a valid ORCID iD")
    return value


class OrcidIn(BaseModel):
    orcid: str

    _o = field_validator("orcid")(_orcid)


class FollowIn(OrcidIn):
    display_name: str = Field(min_length=1, max_length=NAME_MAX)

    @field_validator("display_name")
    @classmethod
    def _name(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("a follow needs the person's name")
        return value


class SeenIn(OrcidIn):
    accessions: list[str] = Field(max_length=SEEN_MAX)

    @field_validator("accessions")
    @classmethod
    def _accessions(cls, values: list[str]) -> list[str]:
        out: list[str] = []
        for v in values:
            v = str(v).strip()
            if not ACCESSION.match(v):
                raise ValueError("not an accession locus knows how to keep")
            if v not in out:
                out.append(v)
        return out


def _follow(row) -> dict:
    return {"orcid": row["orcid"], "display_name": row["display_name"], "followed_at": row["followed_at"], "seen": json.loads(row["seen"])}


def _rows(user_id: int) -> list:
    with Db() as conn:
        return conn.execute("SELECT * FROM follows WHERE user_id = ? AND kind = 'person' ORDER BY id DESC", (user_id,)).fetchall()


@router.get("")
def all_follows(user: User = Depends(users.current_user)) -> dict:
    """Every person the account follows, newest follow first. Reads nothing upstream."""
    return {"follows": [_follow(r) for r in _rows(user.id)], "limits": LIMITS}


@router.post("")
def follow(body: FollowIn, response: Response, user: User = Depends(users.current_user)) -> dict:
    """Follows a person by ORCID (201); following someone already followed changes nothing (200)."""
    with Db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        if conn.execute("SELECT 1 FROM follows WHERE user_id = ? AND kind = 'person' AND orcid = ?", (user.id, body.orcid)).fetchone():
            return {"added": False}
        if conn.execute("SELECT count(*) FROM follows WHERE user_id = ?", (user.id,)).fetchone()[0] >= MAX_FOLLOWS:
            raise ApiError(409, "LIMIT_REACHED", f"An account follows at most {MAX_FOLLOWS} people. Unfollow someone to make room.")
        conn.execute("INSERT INTO follows (user_id, kind, orcid, display_name, followed_at) VALUES (?, 'person', ?, ?, ?)",
                     (user.id, body.orcid, body.display_name, iso(users.now())))
    response.status_code = 201
    return {"added": True}


@router.delete("")
def unfollow(body: OrcidIn, user: User = Depends(users.current_user)) -> dict:
    with Db() as conn:
        if not conn.execute("DELETE FROM follows WHERE user_id = ? AND kind = 'person' AND orcid = ?", (user.id, body.orcid)).rowcount:
            raise ApiError(404, "FOLLOW_NOT_FOUND", "Your account does not follow this person.")
    return {"ok": True}


@router.post("/seen")
def mark_seen(body: SeenIn, user: User = Depends(users.current_user)) -> dict:
    """Marks datasets of a followed person as seen, keeping the newest 500."""
    with Db() as conn:
        row = conn.execute("SELECT * FROM follows WHERE user_id = ? AND kind = 'person' AND orcid = ?", (user.id, body.orcid)).fetchone()
        if not row:
            raise ApiError(404, "FOLLOW_NOT_FOUND", "Your account does not follow this person.")
        old = json.loads(row["seen"])
        seen = (old + [a for a in body.accessions if a not in old])[-SEEN_MAX:]
        conn.execute("UPDATE follows SET seen = ? WHERE id = ?", (json.dumps(seen), row["id"]))
    return {"seen": seen}


@router.get("/updates")
def updates(user: User = Depends(users.current_user)) -> dict:
    """For each followed person (the newest 40 follows), the datasets their ORCID-linked papers deposited or cite, each
    marked new unless seen. status per person: "ok", "failed" (Europe PMC refused or broke), "late" (not read within
    the 45 s budget) or "not_checked" (past the first 40)."""
    rows = _rows(user.id)
    deadline = time.monotonic() + FETCH_SECONDS
    pool = ThreadPoolExecutor(max_workers=FETCH_WORKERS)
    futures = {pool.submit(work, r["orcid"], deadline): r["orcid"] for r in rows[:FETCH_MAX]}
    wait(futures, timeout=FETCH_SECONDS)
    pool.shutdown(wait=False, cancel_futures=True)
    answers: dict[str, tuple[str, dict | None]] = {}
    for future, orcid in futures.items():
        if not future.done() or future.cancelled():
            answers[orcid] = ("late", None)
        elif isinstance(future.exception(), pace.PaceTimeout):
            answers[orcid] = ("late", None)
        elif future.exception() is not None:
            answers[orcid] = ("failed", None)
        else:
            answers[orcid] = ("ok", future.result())
    people = []
    for r in rows:
        status, got = answers.get(r["orcid"], ("not_checked", None))
        entry = _follow(r) | {"status": status}
        if got is not None:
            seen = set(entry["seen"])
            entry |= {"linked": got["linked"], "read": got["read"], "datasets": [d | {"new": d["accession"] not in seen} for d in got["datasets"]]}
            entry["new"] = sum(d["new"] for d in entry["datasets"])
        people.append(entry)
    return {"people": people, "limits": LIMITS}


@public.get("/person/identity")
def person_identity(name: str = Query(min_length=3, max_length=120)) -> dict:
    """Which ORCID a contributor's name stands for, as Europe PMC's ORCID tags show it (see identity())."""
    try:
        return identity(name)
    except (httpx.HTTPError, pace.PaceTimeout, KeyError, ValueError):
        raise ApiError(502, "UPSTREAM_FAILED", "Europe PMC did not answer. Please try again.", transient=True)


def install(app: FastAPI) -> None:
    """Adds /follows/people and /person/identity; call after users.install(app), which provides the error handlers."""
    if "/follows" not in users.SHAPED_PREFIXES:
        users.SHAPED_PREFIXES.append("/follows")
    app.include_router(router)
    app.include_router(public)
