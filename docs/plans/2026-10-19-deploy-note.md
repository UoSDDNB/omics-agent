# Deployment note for the morning of 19 October 2026

Written overnight by the `modalities` build. Nothing on the public server (playtime-vps), the tunnel or the vLLM server
was touched. What follows is what to do, in order, and what to expect.

## What is on branch `modalities`

- The three-row Process panel (here, now / on your laptop / on a cluster) for GEO bulk RNA-seq, single-cell RNA-seq and
  Ribo-seq rows, with requirements per dataset and reasons when a row cannot run; kits as zips.
- Single-cell and Ribo-seq "here, now" analyses of the authors' processed files, and the Ribo-seq laptop path.
- Status and evidence: `docs/plans/2026-10-19-modalities-overnight.md` (status log at the end),
  `docs/evidence/process/{panel,GSE229253,GSE132703}/`, `docs/evidence/qwen/`.

## On the public server (OMICS_PROCESS=cached)

1. Merge or check out `modalities` in the deploy checkout, `uv sync`, `cd web && npm ci && npm run build`, restart the
   API and the web app as they are run today. No schema or index change; `data/` stays as it is.
2. The panel's "Here, now" row runs live on the server for single-cell and Ribo-seq when the authors' files are small
   enough (single-cell: under 400 MB of matrices; Ribo-seq: count tables). These need the micromamba environments
   `omics-sc` (scanpy, leidenalg, python-igraph, kb-python) and `omics-ribo` (bowtie2, samtools, fastp, pysam, seqkit,
   matplotlib) plus the existing `omics-rnaseq` one for DESeq2. On a 2 vCPU / 3.8 GB server the single-cell analysis
   of 8 samples took 3–4 GB peak here, so **either create the environments and accept that a single-cell "here, now"
   run may swap, or do not create them**: without the environments a run fails with a clear error in the panel, and the
   cached GSE229253 and GSE132703 results still show, because `result.json` files under `data/process/<GSE>/<type>-here/`
   are served as "done". To ship the cached showcase runs, copy `data/process/GSE229253/scrnaseq-here/` (without
   `analysed.h5ad`, 168 MB, and `matrices/`) and `data/process/GSE132703/riboseq-here/` and `riboseq-laptop/` (without
   `reads/` and `aligned/`) to the server's `data/process/`.
3. The "On your laptop" row shows the command and a zip on the public server (it never runs there); the "On a cluster"
   row is a zip. Both are built from GEO and ENA at request time (about 1–25 s; ENA is the slow part, remembered for an
   hour per series).
4. Environment: nothing new is required. `OMICS_PROCESS=cached` keeps its meaning. Optional switches for the local model
   (see below) are off unless set.

## Qwen speed

Measured on 19 October against the 18 October baseline (`docs/evidence/qwen/`, ledger and log in the run directory
`~/hillclimb/locus-modalities-20261019`). The switches are environment variables read by `omics_agent/agent.py`.

- **Set on the API process: `LOCAL_LLM_COMPACT_JSON=1`** (accepted, variant 3). vLLM pretty-prints every
  schema-constrained answer, and on pgx the output tokens set a stage's wall time. With this flag the agent sends the
  server an EBNF grammar that allows no newlines or indentation (built from each schema by `scripts/build_grammars.py`
  into `omics_agent/grammars.json`; rebuild it with `uv run --with xgrammar python scripts/build_grammars.py` whenever a
  schema changes, a schema without a grammar falls back to the schema). Over the 9 harness questions: triage 1508 → 549 s,
  screen 1360 → 762 s, wall after planning 3756 → 1440 s; recall on the sure Opus picks 2/7 as before; the demo study
  GSE229705 ranked 3rd (1st before, all top rows graded strong). The prompts do not change, so remembered answers stay valid.
  The same effect server-wide without the flag: start vLLM with `--structured-outputs-config '{"disable_any_whitespace": true}'`
  (not done tonight; the server was not restarted).
- **Leave off: `OMICS_TRIAGE_COMPACT=1`** (rejected, variant 1). Triage 1508 → 260 s, but the one-list form scores more
  coarsely: recall fell to 1/7 and the returned rows overlapped the baseline by only 12–40 per question.
- **Leave off: `OMICS_SCREEN_SHORT=1`** (not run as a full variant; in single-call probes the note changed verdicts).
- `OMICS_SCREEN_BATCH`, `OMICS_TRIAGE_BATCH`, `OMICS_SCREEN_CHARS`, `OMICS_TRIAGE_CHARS`: see the ledger for any batch
  variant measured after variant 3.
- `OMICS_FRESH_ANSWERS=1` is for measurements only: it ignores remembered answers and must not be set in production.
- Robustness fix shipped with this work: a GEO `acc.cgi` server error or dropped connection is retried, and a series whose
  sample records still cannot be fetched is returned without sample counts instead of ending the search (GEO was down for
  about an hour on the morning of 19 October and killed a run).

## Checks after deploying

- `curl "$API/process/GSE273888/options?topic=mTOR%20inhibitor%2C%20rapamycin"` returns three rows, "here" with
  `action: cached` if the earlier run is present.
- `curl "$API/process/GSE132703/run/here?topic=mTOR%20inhibition%2C%20Torin1%20versus%20DMSO"` returns `stage: done`
  if the Ribo-seq showcase run was copied.
- In the browser: search "Matched RNA-seq and Ribo-seq before and after mTOR inhibition", open GSE132703, click
  **Process**, then **Show the results** on "Here, now": the ΔTE scatter should appear (compare
  `docs/evidence/process/panel/GSE132703-here-results-1280.png`).
