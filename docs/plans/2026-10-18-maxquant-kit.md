# MaxQuant search kit for PRIDE datasets

Status: asked for by Juri at 08:15 BST on 18 October 2026. Designed, not built, at the time of writing. Additive: it must not change or risk anything in the demo path.

## Where the idea comes from

`FlynnLachendro/pridemap` (MIT; Juri is one of the copyright holders, so reuse is clean) generates a per-dataset "search kit": scripts that preflight the machine, pull the raw instrument files from PRIDE, fetch the UniProt reference proteome, convert vendor formats where needed, and run MaxQuant in Docker, streaming progress and resuming after an interruption. It also carries an `mqpar.xml` contract with tests and a validator. Read `docs/maxquant-local.md`, `tests/test_mqpar_contract.py` and `tools/mqpar-validate/` there before writing anything.

Credit it the way the web app already credits pridemap: a `LICENSE.pridemap`-style notice naming the MIT licence and its authors, and a line in the README. Prefer re-implementing in this repository's style over copying files, but where a file is taken, keep its notice.

## What locus adds

A **Download MaxQuant kit** action on PRIDE rows, next to the existing samplesheet export, producing a zip containing:

- `mqpar.xml` with the dataset's own parameters filled in: the raw file list, the experiment and fraction assignment taken from the SDRF (phase 2 already parses it), the labelling type from `comment[label]`, the instrument from `comment[instrument]`, the FASTA, and sensible defaults for everything else. Variable and fixed modifications follow the SDRF where it states them.
- `fasta/` fetch script for the UniProt reference proteome matching `characteristics[organism]`.
- `download_raw.sh` for the project's raw files from PRIDE, with checksums where PRIDE publishes them.
- `run_maxquant.sh`, `preflight.sh`, `run_all.sh`: resume-safe, progress to a JSONL file, exits on first failure.
- `README.txt`: what the kit does, the exact commands, the resource requirements, and the honest caveats below.

## The caveat, stated everywhere it appears

**This does not run on a laptop and it does not run here.** MaxQuant needs 8–16 GB of RAM per search and hours to days of CPU, and the published container is x86-64 while this machine is ARM64, so it would run only under emulation. Per `docs/data-processing-contract.md`, proteomics is HPC tier. So:

- The kit is **generated and validated** by locus, and **run by the user** on a cluster or a workstation that meets the requirements.
- The button's label and the README say so plainly. No progress bar, no implication that a search is running.
- Add a Slurm submission script (`submit_slurm.sh`) with the memory, CPU and walltime the search needs, since HPC is where this will actually run.

## Acceptance

1. `mqpar.xml` is generated for three real PRIDE projects with different labelling (one label-free, one TMT, one with fractions) and each passes a schema or contract check; print the diff of the fields that differ between them.
2. The kit's scripts pass `shellcheck` or an equivalent syntax check; `preflight.sh` run here reports the architecture and memory blockers correctly rather than claiming it can proceed.
3. Tests cover the SDRF-to-mqpar mapping, including a project with no SDRF, where the kit must refuse with a clear message rather than guess.
4. `uv run pytest` and `npm run build` pass; the demo path (search, Process, figures) is untouched and still passes.
5. README and the row action both carry the HPC caveat; pridemap is credited with its MIT notice.
6. Committed on a branch off `main`, pushed, with a PR description ready. Do not merge to `main` while the pitch is running.

## Priority

Below everything in the delivery checklist. If the submission or the demo needs attention, stop this and say so.

## Status log

- 2026-10-18 08:15 BST: spec written; no code yet.
