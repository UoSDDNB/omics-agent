# Accounts

locus works without an account. An account keeps what you save on every device you sign in from. This page says what
an account does, what locus stores for it, and what is not built yet.

## Signing in

- **Passkeys.** You create an account by choosing a display name and making a passkey on your phone, computer or
  password manager. locus never sees a password and asks for no email address. Sign in later with the same passkey.
- **Recovery codes.** When the account is created, locus shows ten one-time recovery codes, once. Each signs you in a
  single time if you lose your passkey. locus keeps only their SHA-256 hashes.
- **ORCID.** When the server has an ORCID client (`ORCID_CLIENT_ID`, `ORCID_CLIENT_SECRET`, optional `ORCID_BASE` for
  the sandbox), you can sign in with ORCID or link your iD to an existing account. Without a client the ORCID routes
  answer 404 and the button is hidden. The redirect URI to register with ORCID is `<LOCUS_ORIGIN>/api/account/orcid/callback`.
  An ORCID attempt can only be finished in the browser that started it, and a link only by the account that started it.
- **Signing out** ends the session on the server and removes the cookie. Signing in again in the same browser ends the
  session it had before.

## What locus stores

Account data lives in its own SQLite file, `OMICS_USERS_DB` (default `data/users.db`, not in git), never in
`omics.db`. For each account: the display name and creation time; each passkey's public key, counter, transports,
creation and last-use times; hashed recovery codes; your lists and their items, your watched searches and the people you follow (their ORCID, name and the datasets you marked seen; see below); a linked ORCID iD; sessions (a hash of the cookie token, the
sign-in method, times and the browser's user-agent string); and a short audit trail of sign-ins and changes. locus runs
no analytics.

## Security, for whoever runs the server

- Sessions: a random 32-byte token in an HttpOnly, SameSite=Lax, Path=/ cookie (Secure unless
  `LOCUS_COOKIE_INSECURE=1`, for plain-http localhost only), stored server-side as SHA-256, 30 days from last use.
- Every state-changing account request must be JSON and carry the header `X-Locus-Intent: 1`, else 403
  `INTENT_REQUIRED`.
- Sign-in routes accept at most 10 requests a minute from one address and 100 a minute overall (in-process, so the
  counts reset when the API restarts). Behind the web app's `/api` rewrite the address is read from
  `X-Forwarded-For`, which a client can forge unless a proxy in front rewrites it; the overall cap still holds. A
  public deployment must have a proxy in front of the web app (the Cloudflare tunnel, Caddy or nginx) that appends the
  caller's address to `X-Forwarded-For`, because Next's rewrite keeps whatever header the client sent.
- Passkeys: relying-party id `LOCUS_RP_ID` (default `localhost`) and origin `LOCUS_ORIGIN` (default
  `http://localhost:3000`) must match the address people use. Each challenge works once and for five minutes. User
  verification (PIN, fingerprint or face) is required when creating a passkey and at every sign-in, and a response
  without it is refused, since the passkey is the only factor. A refused passkey gets one fixed message; the reason is
  logged on the server.
- ORCID: `/account/orcid/start` sets a five-minute HttpOnly cookie `locus_orcid` with a random nonce whose hash is
  stored with the OAuth state. The callback refuses a browser without the matching cookie, so a forwarded authorize or
  callback link signs no one in and links nothing. A link attempt also needs the same account to be signed in when
  ORCID sends the browser back.
- `POST /account/dev-login` signs in without a passkey for automated page checks. It exists only when
  `LOCUS_DEV_LOGIN=1` and the API's peer and every hop listed in `X-Forwarded-For` are loopback addresses. Those hops
  are what the header reports: without a proxy in front that appends the real address, a client can forge them, so the
  web app must listen on 127.0.0.1 wherever this flag is set (the page gate does). Never set it on a public server.
- Errors from account routes have one shape: `{"error": {"code", "message", "transient"}}`.

## Saved datasets and lists

- **Save.** Every search result and dataset page has a Save control. One click keeps the dataset in your built-in
  list, Saved; a message offers "Add to a list" and Undo. The arrow beside Save opens the list picker, where you tick
  the lists that should hold the dataset or make a new one.
- **Lists** (`/lists`) shows every list with its count. A list's page (`/lists/<id>`) keeps datasets in the order you
  added them. Each dataset has a note and tags, edited in place with one Save. Named lists can be renamed or deleted
  (after a confirmation); Saved keeps its name and cannot be deleted.
- **Export.** Each list downloads as plain accessions (one a line) or as CSV with the columns accession, title,
  repository, organism, data type, samples, note, tags, added. A cell that starts with `=`, `+`, `-` or `@` gets a
  leading `'` so a spreadsheet shows it as text.
- **What a list keeps.** Besides the accession, note, tags and the time it was added, each item stores what the page
  showed when you saved it: title, repository, organism, data type and sample count. A list renders from that copy and
  never asks a repository; the dataset page has the current record.
- **Limits.** 100 lists an account (Saved included), 500 datasets a list, names up to 120 characters, descriptions up
  to 600, notes up to 10,000, and 12 tags of up to 40 characters an item.
- **Without an account** Save works into this browser only (localStorage `locus:saved`, same item shape, up to 500).
  `/lists` shows that list and says it lives only in this browser; named lists, notes and tags need an account.
- **API** (all need a session; changes need JSON and `X-Locus-Intent: 1`): `GET/POST /lists`, `GET/PATCH/DELETE
  /lists/{id}`, `POST /lists/{id|saved}/items`, `PATCH/DELETE /lists/{id|saved}/items/{accession}`,
  `GET /lists/{id}/export?format=accessions|csv`. Another account's list answers 404, as a missing one does.

## Watched searches

- **Watch.** Above a search's results, "Watch this search" remembers the question, today's date and the datasets the
  search shows. The home page lists your watched searches under "Watching since". Select the control again to stop
  watching.
- **New since.** When a watched search runs again, results it had not shown before are marked "new" and counted next to
  "Watching since". Those datasets then count as seen, so the run after that marks only what arrived after it. Going
  back to the same results (from a dataset page, say) keeps that run's marks.
- **Where they live.** Signed in, watches are kept in your account and follow you to every device. Without an
  account they live in this browser (localStorage `locus:watched`, same shape) and can be brought into an account
  with the panel described below.
- **Limits.** 200 watched searches an account, a question of up to 500 characters, and up to 500 seen datasets a watch
  (past that, the oldest are dropped, and could be marked new again).
- **API** (all need a session; changes need JSON and `X-Locus-Intent: 1`): `GET /follows/questions` (newest first),
  `POST /follows/questions` with `{question, seen}` (starts watching with 201, or for a question already watched adds
  `seen` to what it has seen and keeps its start date, 200), `DELETE /follows/questions` with `{question}` in the body,
  and `POST /follows/questions/import` (below).

## Bringing this browser's saves into an account

- **When.** After you sign in, if this browser still holds datasets you saved or searches you watched as a guest, a
  strip along the bottom of the window says how many of each it has, names up to three of them, and asks whether to add
  them to your account. It sits over the bottom edge of the page, so nothing on the page moves.
- **Add** sends the saved datasets to your account's Saved list and the watched searches to your account, one request
  each, in the order this browser kept them. Adding twice changes nothing: a dataset Saved already holds keeps its note,
  tags and details, and a search the account already watches keeps its date and what it has seen. The browser's copies
  are removed only for what the server confirms it now holds. If Saved would pass 500 datasets or the account 200
  watches, the ones that fit are added and the rest stay in this browser. An entry locus cannot read (a hand-edited
  accession, say) is not sent and stays in this browser. The strip says how many of each, once: after an Add that left
  something behind, it is not offered again to that account.
- **Not now** leaves everything in this browser (saved datasets show on Lists whenever you are signed out) and is
  remembered for this browser and this account (localStorage `locus:import-declined`, a list of account ids). Another
  account signing in from the same browser is asked again.
- **Clear from this browser** removes the guest saves and watches from this browser after a confirmation, for a shared
  computer where they belong to someone else. Guest state belongs to the browser and is seen by whoever uses it.
- **API:** `POST /lists/saved/import` with `{"items": [{accession, snapshot, note?, tags?}, …]}`, at most 500 items,
  and `POST /follows/questions/import` with `{"watches": [{question, since, seen}, …]}`, at most 200, `since` a past
  day as YYYY-MM-DD. Each entry is checked exactly as a single save or watch; one invalid entry refuses the whole batch
  with 422 and adds nothing. Both answer `added`, `already`, `left_out` and `held` (added plus already). Both need a
  session, JSON and `X-Locus-Intent: 1`, and each runs as one transaction that no other change interleaves with.

## Following researchers

- **By ORCID only.** A person page searches Europe PMC by surname and initials, which mixes people who share a name.
  So the page also reads the author lists of the name's newest 100 papers and counts the ORCIDs Europe PMC tags on that
  author. When one ORCID accounts for most of the tagged papers, the page shows it (with the name on the ORCID record)
  and a Follow button. When several ORCIDs share the tagged papers, the page says the name matches several people; when
  none is tagged, it says so. Neither offers Follow. Following a guest opens the sign-in prompt, which brings you back.
- **What following brings.** `/following` lists, for each person, the locus datasets that their ORCID-linked papers
  deposited or cite (Europe PMC `AUTHORID:"<orcid>"`, newest 100 papers, newest paper first). The name search is never
  used, so another person's datasets cannot appear. Each dataset is marked new until you choose "Mark all as seen".
- **Coverage.** Europe PMC links only part of a person's papers to their ORCID, more often the recent ones (29 Oct:
  5 of 42 papers for Carson Thoreen). Both pages say how many, e.g. "Europe PMC links 5 of 42 papers under this name to
  this ORCID; following uses those 5". A dataset from an older paper without the link does not show.
- **Watched searches** are listed on `/following` too, each with its link and the day watching started. The page runs
  none of them (a search uses the model); opening one runs it and marks what is new.
- **Limits.** 200 follows an account. Each visit to `/following` reads the 40 most recent follows, 4 at a time, within
  45 seconds; a person not read in time says so. Each ORCID's answer is kept for 6 hours, so a dataset that arrives in
  Europe PMC or locus shows within that time. Calls to Europe PMC are paced to at most 5 a second and to ORCID at most
  2 a second across the whole server (`omics_agent/pace.py`); `LOCUS_EPMC_BASE` and `LOCUS_ORCID_BASE` point them
  elsewhere (the page checks use fixtures).
- **API:** `GET /person/identity?name=` (anyone); `GET /follows/people`, `POST /follows/people` `{orcid, display_name}`,
  `DELETE /follows/people` `{orcid}`, `POST /follows/people/seen` `{orcid, accessions}`, `GET /follows/people/updates`.
  Changes need a session, JSON and `X-Locus-Intent: 1`. One account cannot read or change another's follows.

## Not built yet

Public lists, settings (renaming, adding or removing passkeys, new recovery codes, unlinking
ORCID, deleting the account) come in later steps. A list cannot be reordered by hand, and the nf-core sample sheet is not offered for a
whole list yet. Email is not used, so following sends no digest; following institutions or topics, and a person without an ORCID, are not supported.
