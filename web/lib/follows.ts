// Following researchers. A person is followed by ORCID only (never by a bare name), and what following brings is the
// datasets locus holds that their ORCID-linked papers deposited or cite. The API is /api/follows/people (signed in)
// and /api/person/identity (anyone: which ORCID a person page's name stands for).
import { API } from "@/lib/api";
import { AccountError } from "@/lib/account";

export type Identity = {
  name: string; query?: string; status: "one" | "several" | "none" | "no_name";
  matched?: number; scanned?: number; tagged?: number; orcids?: number;
  orcid?: string; orcid_name?: string | null; claimed?: number; linked?: number;
};

export type Follow = { orcid: string; display_name: string; followed_at: string; seen: string[] };

export type FollowedDataset = {
  accession: string; source: string; title: string; modality: string; new: boolean;
  paper: { title: string; year: string | null; pmid: string | null; doi: string | null };
};

export type FollowedPerson = Follow & {
  status: "ok" | "failed" | "late" | "not_checked";
  linked?: number; read?: number; datasets?: FollowedDataset[]; new?: number;
};

export const FOLLOW_LIMITS = { follows: 200, checked: 40 };

async function call<T>(method: "GET" | "POST" | "DELETE", path: string, body?: unknown): Promise<T> {
  const init: RequestInit = method === "GET"
    ? { credentials: "same-origin", cache: "no-store" }
    : { method, credentials: "same-origin", headers: { "Content-Type": "application/json", "X-Locus-Intent": "1" }, body: JSON.stringify(body ?? {}) };
  const res = await fetch(`${API}${path}`, init);
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const e = data?.error;
    throw new AccountError(e?.code ?? `HTTP_${res.status}`, e?.message ?? `locus answered ${res.status}. Please try again.`, e?.transient ?? res.status >= 500);
  }
  return data as T;
}

export const identity = (name: string) => call<Identity>("GET", `/person/identity?name=${encodeURIComponent(name)}`);
export const listFollows = () => call<{ follows: Follow[] }>("GET", "/follows/people").then((r) => r.follows);
export const followUpdates = () => call<{ people: FollowedPerson[] }>("GET", "/follows/people/updates").then((r) => r.people);
export const follow = (orcid: string, display_name: string) => call<{ added: boolean }>("POST", "/follows/people", { orcid, display_name });
export const unfollow = (orcid: string) => call<{ ok: boolean }>("DELETE", "/follows/people", { orcid });
export const markSeen = (orcid: string, accessions: string[]) => call<{ seen: string[] }>("POST", "/follows/people/seen", { orcid, accessions });

export const orcidUrl = (orcid: string) => `https://orcid.org/${orcid}`;
export const papers = (n: number) => `${n.toLocaleString()} ${n === 1 ? "paper" : "papers"}`;

// The coverage sentence both pages show: Europe PMC ties only part of a person's papers to their ORCID.
export function coverage(linked: number, matched?: number): string {
  if (matched != null && linked <= matched)
    return `Europe PMC links ${linked.toLocaleString()} of ${papers(matched)} under this name to this ORCID; following uses those ${linked.toLocaleString()}, so no one else's datasets appear.`;
  return `Europe PMC links ${papers(linked)} to this ORCID; following uses only those, so no one else's datasets appear.`;
}
