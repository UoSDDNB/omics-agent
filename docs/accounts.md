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
creation and last-use times; hashed recovery codes; your lists and their items (see below); a linked ORCID iD; sessions (a hash of the cookie token, the
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

## Not built yet

Public lists, following researchers, settings (renaming, adding or removing passkeys, new recovery codes, unlinking
ORCID, deleting the account) and bringing guest data (this browser's saved datasets and watched searches) into an
account come in later steps. A list cannot be reordered by hand, and the nf-core sample sheet is not offered for a
whole list yet. Email is not used.
