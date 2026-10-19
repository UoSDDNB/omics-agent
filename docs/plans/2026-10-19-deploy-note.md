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

See the status log for the measured before-and-after. The switches are environment variables read by `omics_agent/agent.py`:
`OMICS_TRIAGE_COMPACT=1` (scores as one list per batch, a tenth of the triage output tokens),
`OMICS_SCREEN_SHORT=1` (reasons under 15 words, evidence under 10), `OMICS_SCREEN_BATCH`, `OMICS_TRIAGE_BATCH`,
`OMICS_SCREEN_CHARS`, `OMICS_TRIAGE_CHARS`. Set on the API process only the ones the status log says held quality.
`OMICS_FRESH_ANSWERS=1` is for measurements only: it ignores remembered answers and must not be set in production.

## Checks after deploying

- `curl "$API/process/GSE273888/options?topic=mTOR%20inhibitor%2C%20rapamycin"` returns three rows, "here" with
  `action: cached` if the earlier run is present.
- `curl "$API/process/GSE132703/run/here?topic=mTOR%20inhibition%2C%20Torin1%20versus%20DMSO"` returns `stage: done`
  if the Ribo-seq showcase run was copied.
- In the browser: search "Matched RNA-seq and Ribo-seq before and after mTOR inhibition", open GSE132703, click
  **Process**, then **Show the results** on "Here, now": the ΔTE scatter should appear (compare
  `docs/evidence/process/panel/GSE132703-here-results-1280.png`).
