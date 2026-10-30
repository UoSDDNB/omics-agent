"""App-wide pacing for the public services locus reads on a reader's behalf: Europe PMC (at most 5 requests a second)
and the ORCID public API (at most 2 a second). Every call to them in this process takes the next free slot of one
shared clock per service, so a busy page or a /following fetch cannot burst past what the service asks of clients.

The idea (one slot per period for each upstream, shared by the whole app) comes from papertok's
worker/upstream-pace.ts; this is a fresh Python version, not a copy. Where papertok refuses at once with Retry-After,
locus waits for its slot, and refuses only when the slot would come after the caller's deadline.

The base URLs come from the environment (LOCUS_EPMC_BASE, LOCUS_ORCID_BASE) so page checks can point the API at a
local fixture server; unset, they are the real services.
"""

import os
import threading
import time

import httpx

EPMC_DEFAULT = "https://www.ebi.ac.uk/europepmc/webservices/rest"
ORCID_DEFAULT = "https://pub.orcid.org/v3.0"


class PaceTimeout(Exception):
    """The next free slot comes after the caller's deadline."""


class Pace:
    """One request slot every 1/per_second seconds, shared by every thread of the process."""

    def __init__(self, per_second: float, clock=time.monotonic, sleep=time.sleep):
        self.period = 1.0 / per_second
        self.clock, self.sleep = clock, sleep
        self.lock = threading.Lock()
        self.next = 0.0

    def reset(self) -> None:
        with self.lock:
            self.next = 0.0

    def wait(self, deadline: float | None = None) -> None:
        """Takes the next free slot and sleeps until it comes. Raises PaceTimeout (taking nothing) when that slot lies
        after `deadline` (a time on this pace's clock)."""
        with self.lock:
            t = self.clock()
            slot = max(t, self.next)
            if deadline is not None and slot > deadline:
                raise PaceTimeout(f"no slot before the deadline ({slot - t:.1f} s away)")
            self.next = slot + self.period
        if slot > t:
            self.sleep(slot - t)


EUROPE_PMC = Pace(5)
ORCID = Pace(2)


def epmc_base() -> str:
    return os.environ.get("LOCUS_EPMC_BASE", EPMC_DEFAULT).rstrip("/")


def orcid_base() -> str:
    return os.environ.get("LOCUS_ORCID_BASE", ORCID_DEFAULT).rstrip("/")


def _timeout(timeout: float, deadline: float | None) -> float:
    if deadline is None:
        return timeout
    left = deadline - time.monotonic()
    if left <= 0:
        raise PaceTimeout("the deadline has passed")
    return min(timeout, left)


def epmc_get(path: str, params: dict, timeout: float = 30, deadline: float | None = None) -> dict:
    """GET a Europe PMC REST path (e.g. "/search") as JSON, in its pacing slot. httpx errors pass through."""
    EUROPE_PMC.wait(deadline)
    return httpx.get(f"{epmc_base()}{path}", params=params, timeout=_timeout(timeout, deadline)).raise_for_status().json()


def orcid_get(path: str, timeout: float = 15, deadline: float | None = None) -> dict:
    """GET an ORCID public API path (e.g. "/0000-0003-1164-7224/person") as JSON, in its pacing slot."""
    ORCID.wait(deadline)
    return httpx.get(f"{orcid_base()}{path}", headers={"Accept": "application/json"}, timeout=_timeout(timeout, deadline)).raise_for_status().json()
