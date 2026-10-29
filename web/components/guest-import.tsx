"use client";
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { LINK } from "@/components/page-kit";
import { ACCOUNT_EVENT, me } from "@/lib/account";
import { watches } from "@/lib/api";
import { describeError, guestItems, importGuestSaved, type ImportResult } from "@/lib/lists";

// "Not now" is remembered per browser and per account: another account signing in here is still asked.
const DECLINED = "locus:import-declined";

function declined(): number[] {
  try {
    const ids = JSON.parse(localStorage.getItem(DECLINED) ?? "[]");
    return Array.isArray(ids) ? ids.filter((i) => typeof i === "number") : [];
  } catch {
    return [];
  }
}

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

function summary(r: ImportResult): string {
  const parts: string[] = [];
  if (r.added.length) parts.push(`${plural(r.added.length, "dataset", "datasets")} added to Saved.`);
  if (r.already.length) parts.push(r.added.length ? `${r.already.length} ${r.already.length === 1 ? "was" : "were"} already there.` : "Saved already held these datasets.");
  if (r.left_out.length) parts.push(`${plural(r.left_out.length, "dataset", "datasets")} did not fit, since a list holds at most 500, and stayed in this browser.`);
  return parts.join(" ");
}

type Offer = { user: number; saved: number; watched: number };

// Shown once after signing in when this browser still holds a guest's saved datasets (papertok's guest merge, D6).
// Add sends them to the account's Saved in one request; watched searches stay in this browser until accounts keep them.
export function GuestImport() {
  const [offer, setOffer] = useState<Offer | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState<ImportResult | null>(null);

  const check = useCallback(() => {
    // With nothing to offer there is no need to ask who is signed in.
    const who = guestItems().length === 0 ? Promise.resolve(null) : me().then((m) => m.user, () => null);
    who.then((user) => {
      const saved = guestItems().length;
      if (!user || saved === 0 || declined().includes(user.id)) {
        setOffer(null);
        return;
      }
      setOffer({ user: user.id, saved, watched: watches().length });
      setDone(null);
      setError("");
    });
  }, []);

  useEffect(() => {
    check();
    window.addEventListener(ACCOUNT_EVENT, check);
    return () => window.removeEventListener(ACCOUNT_EVENT, check);
  }, [check]);

  if (!offer && !done) return null;

  const add = async () => {
    setBusy(true);
    setError("");
    try {
      setDone(await importGuestSaved());
      setOffer(null);
    } catch (e) {
      setError(describeError(e));
    } finally {
      setBusy(false);
    }
  };

  const notNow = () => {
    if (offer) localStorage.setItem(DECLINED, JSON.stringify([...new Set([...declined(), offer.user])]));
    setOffer(null);
  };

  return (
    <section aria-labelledby="guest-import" data-guest-import={done ? "done" : "offer"} className="mx-auto mb-10 grid w-full max-w-4xl gap-3 rounded-lg border border-rule bg-card px-5 py-4 text-[14px]">
      <h2 id="guest-import" className="font-display text-[22px] leading-tight">
        {done ? "Added to your account" : "Bring this browser’s saves into your account?"}
      </h2>
      {done ? (
        <>
          <p className="text-muted-foreground" data-import-result>
            {summary(done)}
          </p>
          <p className="flex items-baseline gap-4">
            <Link href={`/lists/${done.list_id}`} className={LINK} onClick={() => setDone(null)}>Open Saved</Link>
            <button type="button" className={LINK} onClick={() => setDone(null)}>Close</button>
          </p>
        </>
      ) : offer && (
        <>
          <p className="text-muted-foreground" data-import-counts={`${offer.saved},${offer.watched}`}>
            This browser has {plural(offer.saved, "saved dataset", "saved datasets")}
            {offer.watched > 0 && ` and ${plural(offer.watched, "watched search", "watched searches")}`}.
            {" "}Add the saved datasets to your Saved list?
            {offer.watched > 0 && " Watched searches stay in this browser for now; a later version of locus will keep them in your account."}
          </p>
          {error && <p role="alert" className="text-[13px] text-destructive">{error}</p>}
          <p className="flex items-center gap-3">
            <Button type="button" disabled={busy} onClick={add}>{busy ? "Adding…" : "Add"}</Button>
            <Button type="button" variant="outline" disabled={busy} onClick={notNow}>Not now</Button>
          </p>
        </>
      )}
    </section>
  );
}
