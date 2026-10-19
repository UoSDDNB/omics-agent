# Qwen search profiling, 18–19 October 2026

Model: Qwen3.8-27B (FP8) served by vLLM on pgx (`LOCAL_LLM_URL`, thinking off). Index: the full local index
(888,335 datasets). Script: `scripts/qwen_baseline.py`; comparison: `scripts/qwen_compare.py`.

Each folder holds `results.json` (per question: wall seconds, seconds per stage, every model call with its stage, seconds
and tokens in and out, the rows returned with their grade, recall against the Opus picks, and for the demo question the
ranks of GSE229705 and GSE229253) and `summary.md` (the table).

| Folder | What | Conditions |
|---|---|---|
| `baseline/` | The 8 harness questions and the demo-study question, triage and screen answers asked afresh (`OMICS_FRESH_ANSWERS=1`), plans and labels cached as in the app | 21:55–23:12 BST; questions 3, 6 and 7 overlapped with other model users (a browser search and two pipeline builders), so their times are inflated |
| `compact-short/` | q1, q2, q3, q7 and the demo with `OMICS_TRIAGE_COMPACT=1 OMICS_SCREEN_SHORT=1` | 23:21–23:41 BST, quiet server; plans and labels cached from the baseline |
| `baseline-quiet/` | q1, q2, q7 and the demo with the baseline configuration again | after 23:42 BST, quiet server; the run-to-run noise control |

Recall is against the Opus 5.5 picks that this repository names (`progress.md`, `docs/evaluation.md`,
`docs/evidence/phase0/`): 7 "sure" (GSE36892, GSE35469; GSE69352, GSE100007; GSE136831; PXD058312; PXD020186) and
3 "probable" (PXD028149, PXD017210, MSV000084172). The full list of 34 from the 17–18 October night lived in
`/tmp/locus-night` on the laptop that ran it and is not in the repository.

What the baseline showed: the model decodes a single stream at about 5–7 tokens/s, so a stage's wall time is set by the
output tokens of its longest call; triage's `{n, score}` objects cost about 550 tokens a call, screening's reasons and
evidence about 460 tokens a call. The compact triage format (one list of scores) was returned with the wrong length in
most batches and fell back to the numbered form, so it bought nothing and stays off. The short screening note (reasons
under 15 words, evidence under 10) cut screening output tokens by about a fifth; whether it is kept is decided against
the noise control in the status log of `docs/plans/2026-10-19-modalities-overnight.md`.
