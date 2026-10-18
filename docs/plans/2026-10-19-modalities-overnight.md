# Overnight 18–19 October: processing for more data types, honest about where it can run

Status: agreed with Juri at 21:45 BST on 18 October 2026. Designed, not built, at the time of writing. Branch `modalities` off `deploy-public` (PR #2), worktree `/home/jlw/omics-agent-modalities`.

## Where things stand

- A public site runs at https://locus.204.168.183.57.sslip.io (playtime-vps: 2 vCPU, 3.8 GB RAM + 4 GB swap). It searches the full index (888,335 datasets, 18 repositories). New searches run on pgx's Qwen through a private tunnel. Process serves precomputed runs only (`OMICS_PROCESS=cached`).
- Bulk RNA-seq processing works on a laptop: subsampled ENA reads → salmon → `.count` files → DESeq2 → five figures (`omics_agent/process.py`, `deseq2.R`).
- The search for the demo question found GSE229705 (bulk RNA-seq) 1st and its single-nucleus half GSE229253 2nd, in 6 min 35 s on Qwen: planning 89 s, **screening 225 s**, facts 77 s.

## Decisions recorded tonight

1. **Every data type presents its compute options the same way: three rows**, each with what it costs *for this dataset* (time, memory, disk) and an honest label.

   | Row | Meaning |
   |---|---|
   | **Here, now** | Small analyses of files that are already processed (the authors' tables, a showcase run). Instant, and safe on the public server. |
   | **On your laptop** | A kit (one command, or a zip of scripts) that a 16 GB laptop can run, with locus checking the dataset fits before the user starts. |
   | **On a cluster** | A Slurm / nf-core kit, with a one-line reason a laptop cannot do it (for example "a human STAR index needs about 32 GB of memory"). |

   locus never pretends: a row that cannot work for this dataset is shown greyed with its reason, not hidden.

2. **Tonight's data types**, in priority order:
   1. **Bulk RNA-seq, cluster row**: the nf-core/rnaseq kit (STAR + salmon) for what already runs on a laptop, so the existing type shows all three rows.
   2. **Single-cell RNA-seq**: here, now = QC, clustering, UMAP, marker genes and pseudobulk differential expression from the authors' processed matrix when it is small enough; laptop = kb-python counts from subsampled reads, then the same analysis with scanpy; cluster = nf-core/scrnaseq kit. Test on GSE229253, the demo study's single-nucleus half.
   3. **Ribo-seq and translation efficiency**: cluster = nf-core/riboseq kit (samplesheet export already exists in `samplesheet.py`); laptop = the path the contract designed but nobody built (rRNA removal with bowtie2, alignment to the transcriptome, CDS counts, P-site offsets where the footprint length allows); with a matched RNA-seq library, translation efficiency and ΔTE using DESeq2 with an interaction term (the deltaTE approach). Test on GSE132703, whose Ribo-seq and RNA-seq libraries locus already pairs.
   Proteomics waits; the MaxQuant kit lives on the `maxquant-kit` branch.

3. **Qwen speed, quality first, cost second.** Thinking is already off by default (`LOCAL_LLM_THINK` is opt-in), so the time is in the number and size of calls, mostly screening. Measure before changing anything, and keep any change only if search quality holds.

## Work, in order

### 0. Baseline

- Point this worktree at the full index (`data/` → `/home/jlw/locus-data`, fetched from the `data-2026-10-18` release; checksums verified).
- Run Hridya's harness questions on Qwen and record, per question: wall time per stage, number of model calls, tokens in and out, and recall against the Opus list in `docs/evaluation.md`. This is the quality bar every speed change must meet.

### 1. The three-row panel

One Process panel component for every data type, driven by an API that returns, per dataset, which rows apply, their requirements and the reason when a row does not. Requirements are estimated from ENA's read counts and file sizes, calibrated against measured runs (GSE273888 took 172 s; GSE295999 and GSE344137 timings are in `/tmp/demo-*.log` and their `process.log`). The public server (`OMICS_PROCESS=cached`) shows "Here, now" live and the other two rows as kits.

### 2. Bulk RNA-seq cluster kit

A zip: nf-core/rnaseq samplesheet built from the same GEO records and ENA runs as the laptop path, a Slurm submission script with stated memory and walltime, a minimal Nextflow config with an Apptainer profile, and a README naming the reference (GENCODE release) so results match the laptop tier's annotation.

### 3. Single-cell

As in decision 2. A UMAP and a dot plot of marker genes are the figures; pseudobulk DE per cell type is the comparison, and the nested-in-people warning that already exists applies to it.

### 4. Ribo-seq and TE

As in decision 2. The figures that matter to a translation researcher: a metagene plot around start and stop codons showing three-nucleotide periodicity, a footprint-length histogram, and a ΔTE scatter (Δ RNA vs Δ Ribo, coloured by class: translationally regulated, buffered, transcriptional). State plainly when the laptop path is a lower-fidelity approximation of the cluster pipeline.

### 5. Qwen speed

Profile the screening stage first. Candidates, each tested against the baseline: fewer or shorter screening calls, smaller per-call token budgets, batching datasets per call, the concurrency the vLLM server actually sustains. Keep a change only if harness recall is at least the baseline and the demo question still ranks GSE229705 and GSE229253 at the top.

## Rules

- **Do not touch the public server** (playtime-vps), the tunnel (`~/locus-tunnel.sh`, tmux `locus-tunnel`), or the vLLM server on port 8000. Leave a deployment note for the morning instead.
- Work only in `/home/jlw/omics-agent-modalities` on branch `modalities`; test servers on ports 8040 and 3040; never touch `main` or other worktrees.
- pgx is ARM64: tools come from bioconda/conda-forge `linux-aarch64` through `~/bin/micromamba` with `MAMBA_ROOT_PREFIX=/home/jlw/.local/share/mamba`. If a tool has no ARM64 build, say so and choose another; do not pretend a kit was tested when it was not.
- riboseq-agent (private, unlicensed) is ideas only; copy no code. Use the open-source tools themselves (nf-core, kb-python, scanpy, bowtie2, DESeq2, riboWaltz or an equivalent) under their licences.
- Testing a cluster kit for real on Iridis is optional and last: at most one small subsampled run, submitted with `sbatch`, nothing heavy on login nodes.
- Never report a number or a figure that was not produced in this run.

## Status log

- 2026-10-18 21:50 BST: spec written; worktree created; index fetching to `/home/jlw/locus-data`.
