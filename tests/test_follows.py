"""Following researchers (F5): ORCID resolution with the several-people guard, follow / unfollow / mark seen, the
/updates feed (ORCID-linked papers only, new until seen, bounded and cached), app-wide upstream pacing, and that one
account can neither see nor change another's follows. Every Europe PMC and ORCID call is answered by a fake; no network."""

import threading
import time

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from omics_agent import follows, pace, saved, store, users, watches

INTENT = {"X-Locus-Intent": "1"}
LOCAL = ("127.0.0.1", 50000)
THOREEN = "0000-0003-1164-7224"
SMITH_A = "0000-0002-1825-0097"
SMITH_B = "0000-0001-5000-0007"
COAUTHOR = "0000-0002-2222-3331"


def author(last, initials, orcid=None):
    a = {"fullName": f"{last} {initials}", "lastName": last, "initials": initials}
    if orcid:
        a["authorId"] = {"type": "ORCID", "value": orcid}
    return a


def paper(pmid, year, authors):
    return {"id": pmid, "source": "MED", "pmid": pmid, "title": f"Paper {pmid}.", "pubYear": year, "authorList": {"author": authors}}


# Name query "Thoreen CC": 42 hits, of the newest 6 five tag the ORCID on Thoreen and one tags none.
THOREEN_NAME = [paper(str(1000 + i), str(2024 - i), [author("Watson", "MJ"), author("Thoreen", "CC", THOREEN)]) for i in range(1, 6)] + [
    paper("2001", "2012", [author("Thoreen", "CC")])]
THOREEN_ORCID = [paper(str(1000 + i), str(2024 - i), []) for i in range(1, 6)]
# Two people named "Smith J": three papers tag one ORCID and three another.
SMITH_NAME = [paper(f"30{i}", "2020", [author("Smith", "J", SMITH_A)]) for i in range(3)] + [paper(f"31{i}", "2021", [author("Smith", "J", SMITH_B)]) for i in range(3)]
# "Nobody X": only a co-author carries an ORCID, which says nothing about Nobody.
NOBODY_NAME = [paper("401", "2022", [author("Nobody", "X"), author("Other", "Y", COAUTHOR)])]


class Upstream:
    """Answers Europe PMC searches and ORCID person records from the fixtures above, and counts the calls."""

    def __init__(self):
        self.calls: list[str] = []
        self.lock = threading.Lock()
        self.fail: set[str] = set()
        self.delay = 0.0
        self.active = self.peak = 0

    def get(self, url, params=None, headers=None, timeout=None):
        with self.lock:
            self.calls.append(url + " " + str((params or {}).get("query", "")))
            self.active += 1
            self.peak = max(self.peak, self.active)
        try:
            if self.delay:
                time.sleep(self.delay)
            return self._answer(url, params or {})
        finally:
            with self.lock:
                self.active -= 1

    def _answer(self, url, params):
        request = httpx.Request("GET", url)
        if "/orcid/" in url:
            body = {"name": {"given-names": {"value": "Carson"}, "family-name": {"value": "Thoreen"}, "credit-name": None}}
            return httpx.Response(200, json=body, request=request)
        query = params["query"]
        if any(f in query for f in self.fail):
            return httpx.Response(503, json={}, request=request)
        found, hits = {
            'AUTH:"Thoreen CC"': (THOREEN_NAME, 42),
            f'AUTHORID:"{THOREEN}"': (THOREEN_ORCID, 5),
            'AUTH:"Smith J"': (SMITH_NAME, 900),
            'AUTH:"Nobody X"': (NOBODY_NAME, 1),
        }.get(query, ([], 0))
        if query.startswith("AUTHORID:") and not found:
            orcid = query.split('"')[1]
            found, hits = [paper(f"9{abs(hash(orcid)) % 10000}", "2023", [])], 1
        return httpx.Response(200, json={"hitCount": hits, "resultList": {"result": found[: int(params.get("pageSize", 25))]}}, request=request)


@pytest.fixture
def up(tmp_path, monkeypatch):
    monkeypatch.setenv("OMICS_USERS_DB", str(tmp_path / "users.db"))
    monkeypatch.setenv("LOCUS_DEV_LOGIN", "1")
    monkeypatch.setenv("LOCUS_EPMC_BASE", "http://fixture.invalid/epmc")
    monkeypatch.setenv("LOCUS_ORCID_BASE", "http://fixture.invalid/orcid")
    monkeypatch.delenv("LOCUS_COOKIE_INSECURE", raising=False)
    monkeypatch.setattr(store, "DB", tmp_path / "omics.db")
    db = store.connect()
    store.upsert(db, [
        {"accession": a, "source": "GEO", "title": t, "summary": "", "organism": "Homo sapiens", "modality": "Expression profiling by high throughput sequencing",
         "samples": 4, "published": "2024-01-01", "papers": p, "url": ""}
        for a, t, p in [("GSE900101", "Ribosome profiling after Torin1", ["pmid:1001"]), ("GSE900103", "Polysomes in HEK293", ["pmid:1003"]),
                        ("GSE900199", "Name-only paper's dataset", ["pmid:2001"])]
    ])
    db.commit()
    db.close()
    fake = Upstream()
    monkeypatch.setattr(pace.httpx, "get", fake.get)
    monkeypatch.setattr(pace, "EUROPE_PMC", pace.Pace(10_000))
    monkeypatch.setattr(pace, "ORCID", pace.Pace(10_000))
    follows.clear_caches()
    users.AUTH_LIMIT.reset()
    yield fake
    follows.clear_caches()


def make_app() -> FastAPI:
    app = FastAPI()
    users.install(app)
    saved.install(app)
    watches.install(app)
    follows.install(app)
    return app


def signed_in(name="Gate") -> TestClient:
    c = TestClient(make_app(), base_url="https://testserver", client=LOCAL)
    assert c.post("/account/dev-login", json={"display_name": name}, headers=INTENT).status_code == 200
    return c


def call(c, method, path, body=None):
    return c.request(method, path, json=body if body is not None else {}, headers=INTENT)


# ---------------------------------------------------------------- who a name is


def test_one_orcid_for_most_tagged_papers_is_named_with_its_coverage(up):
    c = TestClient(make_app(), base_url="https://testserver", client=LOCAL)
    r = c.get("/person/identity", params={"name": "Carson C Thoreen"})
    assert r.status_code == 200
    got = r.json()
    assert got["status"] == "one" and got["orcid"] == THOREEN
    assert got["matched"] == 42 and got["linked"] == 5 and got["claimed"] == 5 and got["tagged"] == 5
    assert got["orcid_name"] == "Carson Thoreen"
    # The co-author's ORCID on the same papers (Watson) is not counted: there is none, and Thoreen's alone is.
    assert got["orcids"] == 1


def test_two_people_sharing_a_name_get_no_orcid(up):
    got = TestClient(make_app(), client=LOCAL).get("/person/identity", params={"name": "John Smith"}).json()
    assert got["status"] == "several" and "orcid" not in got
    assert got["orcids"] == 2 and got["tagged"] == 6


def test_a_coauthors_orcid_says_nothing_about_the_person(up):
    got = TestClient(make_app(), client=LOCAL).get("/person/identity", params={"name": "Xavier Nobody"}).json()
    assert got["status"] == "none" and "orcid" not in got


def test_identity_is_cached_and_reports_upstream_failure(up):
    c = TestClient(make_app(), client=LOCAL)
    c.get("/person/identity", params={"name": "Carson C Thoreen"})
    n = len(up.calls)
    assert c.get("/person/identity", params={"name": "Thoreen, Carson C."}).json()["orcid"] == THOREEN
    assert len(up.calls) == n
    up.fail.add("Smith")
    r = c.get("/person/identity", params={"name": "John Smith"})
    assert r.status_code == 502 and r.json()["error"]["code"] == "UPSTREAM_FAILED"


# ---------------------------------------------------------------- follow, unfollow, seen


def test_follow_feed_uses_orcid_linked_papers_only_and_marks_new_until_seen(up):
    c = signed_in()
    assert call(c, "POST", "/follows/people", {"orcid": THOREEN, "display_name": "Carson Thoreen"}).status_code == 201
    assert call(c, "POST", "/follows/people", {"orcid": f"https://orcid.org/{THOREEN}", "display_name": "Carson Thoreen"}).status_code == 200
    assert [f["orcid"] for f in c.get("/follows/people").json()["follows"]] == [THOREEN]

    feed = c.get("/follows/people/updates").json()["people"]
    assert len(feed) == 1 and feed[0]["status"] == "ok" and feed[0]["linked"] == 5
    # Newest paper first (1001 is 2023, 1003 is 2021); the name-only paper's dataset never appears.
    assert [d["accession"] for d in feed[0]["datasets"]] == ["GSE900101", "GSE900103"]
    assert all(d["new"] for d in feed[0]["datasets"]) and feed[0]["new"] == 2
    assert feed[0]["datasets"][0]["paper"]["pmid"] == "1001"

    assert call(c, "POST", "/follows/people/seen", {"orcid": THOREEN, "accessions": ["GSE900101"]}).json()["seen"] == ["GSE900101"]
    feed = c.get("/follows/people/updates").json()["people"]
    assert {d["accession"]: d["new"] for d in feed[0]["datasets"]} == {"GSE900101": False, "GSE900103": True}

    assert call(c, "DELETE", "/follows/people", {"orcid": THOREEN}).json() == {"ok": True}
    assert c.get("/follows/people").json()["follows"] == []
    assert call(c, "DELETE", "/follows/people", {"orcid": THOREEN}).status_code == 404


def test_follow_validates_orcid_and_name_and_needs_session_and_intent(up):
    guest = TestClient(make_app(), base_url="https://testserver", client=LOCAL)
    assert guest.get("/follows/people").status_code == 401
    assert call(guest, "POST", "/follows/people", {"orcid": THOREEN, "display_name": "x"}).status_code == 401
    c = signed_in()
    r = c.post("/follows/people", json={"orcid": THOREEN, "display_name": "x"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "INTENT_REQUIRED"
    assert call(c, "POST", "/follows/people", {"orcid": "0000-0003-1164-7225", "display_name": "x"}).status_code == 422  # bad check digit
    assert call(c, "POST", "/follows/people", {"orcid": THOREEN, "display_name": "   "}).status_code == 422
    assert call(c, "POST", "/follows/people/seen", {"orcid": THOREEN, "accessions": ["not an accession"]}).status_code == 422


def test_one_account_cannot_see_or_change_anothers_follows(up):
    alice, bob = signed_in("Alice"), signed_in("Bob")
    assert call(alice, "POST", "/follows/people", {"orcid": THOREEN, "display_name": "Carson Thoreen"}).status_code == 201
    assert bob.get("/follows/people").json()["follows"] == []
    assert bob.get("/follows/people/updates").json()["people"] == []
    assert call(bob, "DELETE", "/follows/people", {"orcid": THOREEN}).status_code == 404
    assert call(bob, "POST", "/follows/people/seen", {"orcid": THOREEN, "accessions": ["GSE900101"]}).status_code == 404
    mine = alice.get("/follows/people").json()["follows"]
    assert [f["orcid"] for f in mine] == [THOREEN] and mine[0]["seen"] == []


def test_follow_limit(up, monkeypatch):
    monkeypatch.setattr(follows, "MAX_FOLLOWS", 2)
    c = signed_in()
    for orcid in (SMITH_A, SMITH_B):
        assert call(c, "POST", "/follows/people", {"orcid": orcid, "display_name": "Smith"}).status_code == 201
    r = call(c, "POST", "/follows/people", {"orcid": THOREEN, "display_name": "Thoreen"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "LIMIT_REACHED"


# ---------------------------------------------------------------- bounded fetch


def orcids(n):
    out, i = [], 0
    while len(out) < n:
        base = f"0000-0001-{6000 + i // 10:04d}-{i % 10:03d}"
        out += [base + ch for ch in "0123456789X" if follows.valid_orcid(base + ch)][:1]
        i += 1
    return out


def test_updates_read_at_most_40_follows_4_at_a_time_and_cache_them(up, monkeypatch):
    monkeypatch.setattr(follows, "MAX_FOLLOWS", 50)
    c = signed_in()
    many = orcids(41)
    for o in many:
        assert call(c, "POST", "/follows/people", {"orcid": o, "display_name": "Someone"}).status_code == 201
    up.delay = 0.02
    people = c.get("/follows/people/updates").json()["people"]
    statuses = [p["status"] for p in people]
    assert statuses.count("ok") == 40 and statuses[-1] == "not_checked" and people[-1]["orcid"] == many[0]  # oldest follow left out
    assert up.peak <= 4
    n = len(up.calls)
    c.get("/follows/people/updates")
    assert len(up.calls) == n  # all 40 answers kept for 6 hours


def test_updates_stop_at_the_deadline_and_report_failures(up, monkeypatch):
    c = signed_in()
    for o in (SMITH_A, SMITH_B):
        call(c, "POST", "/follows/people", {"orcid": o, "display_name": "Smith"})
    up.fail.add(SMITH_A)
    got = {p["orcid"]: p["status"] for p in c.get("/follows/people/updates").json()["people"]}
    assert got == {SMITH_A: "failed", SMITH_B: "ok"}

    follows.clear_caches()
    up.fail.clear()
    up.delay = 0.5
    monkeypatch.setattr(follows, "FETCH_SECONDS", 0.1)
    start = time.monotonic()
    got = {p["orcid"]: p["status"] for p in c.get("/follows/people/updates").json()["people"]}
    assert time.monotonic() - start < 0.45
    assert set(got.values()) == {"late"}


# ---------------------------------------------------------------- pacing


class FakeClock:
    def __init__(self):
        self.t = 100.0
        self.slept: list[float] = []

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.slept.append(round(s, 6))
        self.t += s


def test_pace_spaces_calls_one_slot_per_period():
    clock = FakeClock()
    p = pace.Pace(5, clock=clock, sleep=clock.sleep)
    for _ in range(4):
        p.wait()
    assert clock.slept == [0.2, 0.2, 0.2]
    clock.t += 5  # idle time is not banked as a burst
    p.wait()
    p.wait()
    assert clock.slept[-1] == 0.2 and len(clock.slept) == 4


def test_pace_refuses_a_slot_after_the_deadline():
    clock = FakeClock()
    p = pace.Pace(2, clock=clock, sleep=clock.sleep)
    p.wait()
    with pytest.raises(pace.PaceTimeout):
        p.wait(deadline=clock.t + 0.1)  # next slot is 0.5 s away
    p.wait(deadline=clock.t + 0.6)
    assert clock.slept == [0.5]


def test_pace_is_shared_across_threads():
    p = pace.Pace(50)
    stamps: list[float] = []
    lock = threading.Lock()

    def go():
        p.wait()
        with lock:
            stamps.append(time.monotonic())

    threads = [threading.Thread(target=go) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    stamps.sort()
    assert stamps[-1] - stamps[0] >= 5 * 0.02 - 0.005


def test_every_europe_pmc_and_orcid_call_is_paced(up, monkeypatch):
    taken: list[str] = []

    class Counting(pace.Pace):
        def __init__(self, name):
            super().__init__(10_000)
            self.name = name

        def wait(self, deadline=None):
            taken.append(self.name)
            super().wait(deadline)

    monkeypatch.setattr(pace, "EUROPE_PMC", Counting("epmc"))
    monkeypatch.setattr(pace, "ORCID", Counting("orcid"))
    TestClient(make_app(), client=LOCAL).get("/person/identity", params={"name": "Carson C Thoreen"})
    assert taken.count("epmc") == 2 and taken.count("orcid") == 1 and len(up.calls) == 3
