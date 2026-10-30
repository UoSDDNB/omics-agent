// What locus keeps for an account, as the /privacy page and the Privacy section of /settings state it (F7-r1-2).
// This module is the one source of truth for the user-facing facts; docs/accounts.md ("What locus stores") points
// here for the wording users read and keeps the operator detail. Change both when the users DB changes.

export const PRIVACY_PATH = "/privacy";

// One paragraph for /settings.
export const PRIVACY_SUMMARY =
  "For an account, locus keeps your display name, the public half of each passkey, scrambled copies of your recovery codes and sign-in tokens, which browser each sign-in came from, your ORCID iD if you link one, your lists with their notes and tags, your watched searches, the people you follow, and a short log of account events such as sign-ins. It runs no analytics. It sets one cookie that keeps you signed in, and a short-lived one during an ORCID sign-in.";

export type PrivacyFact = { id: string; title: string; body: string[] };

export const PRIVACY_FACTS: PrivacyFact[] = [
  {
    id: "without-an-account",
    title: "Without an account",
    body: [
      "Searching and reading dataset pages need no account. Datasets you save without one stay in this browser's local storage and never reach the server until you sign in and choose to bring them into an account.",
    ],
  },
  {
    id: "what-is-kept",
    title: "What locus keeps for an account",
    body: [
      "Your display name and when the account was made.",
      "Each passkey's public half, its name, when it was added and last used. The private half stays on your device or in your password manager.",
      "Your recovery codes as SHA-256 hashes only. locus shows the codes once and cannot show them again.",
      "Sessions: a hash of the sign-in token, how you signed in, when, and which browser each sign-in came from (its user-agent string).",
      "Your ORCID iD, if you link one.",
      "Your lists with their items, notes and tags, and the public copy of any list you share.",
      "Your watched searches and the people you follow, with the datasets you marked as seen.",
      "A short log of account events such as sign-ins, new passkeys and new recovery codes.",
    ],
  },
  {
    id: "cookies",
    title: "Cookies and tracking",
    body: [
      "locus sets one cookie that keeps you signed in, and a short-lived one (five minutes) during an ORCID sign-in. Both are HttpOnly and first-party.",
      "It runs no analytics and shows no adverts. It asks for no email address.",
    ],
  },
  {
    id: "where",
    title: "Where it is kept",
    body: [
      "Account data lives in its own database file on the server that runs locus, apart from the public dataset catalogue. It is not shared or sold.",
      "An ORCID sign-in asks ORCID only for your iD and name. To show what is new from the people you follow, the server looks up their ORCID iDs in Europe PMC; your own identity is not part of that request.",
    ],
  },
  {
    id: "your-copy",
    title: "Your copy, and deleting it",
    body: [
      "Settings has Download everything as JSON: every row kept about your account, without secrets such as token hashes, code hashes and passkey keys.",
      "Deleting the account in Settings removes all of the above in one step, signs out every device and makes your public links stop opening. One log row stays with the time and \"account deleted\", and nothing in it points at you.",
    ],
  },
];
