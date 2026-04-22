# ARCHITECTURE.md — Geopolitical Risk Assessment Pipeline

## Table of Contents

- [System Overview](#system-overview)
- [Pipeline Diagram](#pipeline-diagram)
- [Component Responsibilities](#component-responsibilities)
- [Stage 1: Triage Layer](#stage-1-triage-layer)
- [Stage 2: Classification Layer](#stage-2-classification-layer)
- [Post-Processing Layer](#post-processing-layer)
- [Concurrency Model](#concurrency-model)
- [External Dependencies](#external-dependencies)
- [Error Handling](#error-handling)

---

## System Overview

The pipeline is a **two-stage batch processing system** designed around a single principle: apply cheap deterministic filters first, then apply expensive LLM inference only to articles that have passed relevance checks.

All components are stateless between pipeline runs. The only persistent artefacts are:
- The taxonomy embedding cache (`data/.taxonomy_cache.pkl`) avoids recomputing taxonomy embeddings on every startup
- The final `outputs/result.csv`

---

## Pipeline Diagram

```text
┌──────────────────────────────────────────────────────────┐
│                        INPUT                             │
│                  data/newsdata.csv                       │
│         Validated on load — missing columns raise        │
│         EnvironmentError before any processing begins    │
└────────────────────────┬─────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────┐
│              STAGE 1 — TRIAGE  (triage.py)               │
│                                                          │
│  Step 1: Keyword Filter (deterministic, zero API cost)   │
│  └─ Regex word-boundary match against EVENT_TAXONOMY     │
│     No match → article rejected, no API call made        │
│                                                          │
│  Step 2: Negative Semantic Filter (Embedding)            │
│  └─ Taxonomy centroids loaded from disk cache or         │
│     computed once and cached (data/.taxonomy_cache.pkl)  │
│  └─ Embed article via text-embedding-3-small             │
│  └─ Compare cosine similarity to positive + negative     │
│     centroids (thresholds from config.py)                │
│  └─ REJECT if negative similarity exceeds positive       │
│     AND negative similarity > NEGATIVE_SIM_THRESHOLD     │
│                                                          │
└────────────────────────┬─────────────────────────────────┘
                         │  ~15–30% of input articles
                         ▼
┌──────────────────────────────────────────────────────────┐
│           STAGE 2 — CLASSIFICATION (classifier.py)       │
│                                                          │
│  prompt_builder.py                                       │
│  └─ Truncate content to MAX_CONTENT_TOKENS (700) using   │
│     tiktoken — exact token count, not character count    │
│  └─ Build Chain-of-Thought prompt with:                  │
│     • Scoring rubric (0.0/1.0 anchors on all 4 scores)  │
│     • Calibration rules (prevent rhetoric inflation)     │
│     • System persona in system message                   │
│                                                          │
│  classifier.py (ASYNC via ThreadPoolExecutor)            │
│  └─ Call gpt-4o-mini, temperature=0.0, max_tokens=350    │
│  └─ Pydantic schema with ge=0.0, le=1.0 constraints      │
│  └─ Retry on RateLimitError: backoff 1s → 2s → 4s       │
│  └─ Non-retryable errors → return None → fallback path   │
│                                                          │
└────────────────────────┬─────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────┐
│         POST-PROCESSING — SCORING  (scoring.py)          │
│                                                          │
│  LLM success path:                                       │
│  risk_score = 0.45(phys) + 0.35(esc) + 0.20(evid)       │
│  confidence = 0.5(evid) + 0.3(sig) + 0.2(model)         │
│  processing_status = 'success'                           │
│                                                          │
│  API failure path (fallback):                            │
│  calculate_fallback_scores(detected_keywords)            │
│  → heuristic scores from keyword severity               │
│  processing_status = 'fallback'                          │
│                                                          │
│  Triage rejected:                                        │
│  risk_score = 0.0, confidence = 'low'                    │
│  processing_status = 'triage_rejected'                   │
│                                                          │
└────────────────────────┬─────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────┐
│                       OUTPUT                             │
│                  outputs/result.csv                      │
│  Original columns + event_labels | risk_score |          │
│  confidence | rationale | keywords_detected |            │
│  processing_status                                       │
│  Rows reconstructed in original order via index map      │
└──────────────────────────────────────────────────────────┘
```

---

## Component Responsibilities

| File | Role | Key Inputs / Outputs |
|---|---|---|
| `main.py` | Orchestrator and CLI entry point | Reads args, calls triage → classify → score → write; index-based sort for O(n) reordering |
| `config.py` | Single source of truth | Keyword taxonomy, model names, all thresholds and weights as named constants |
| `io_csv.py` | I/O with validation | CSV load with required-column check; enriched records → CSV |
| `triage.py` | Stage 1 filter | Keyword regex + negative embedding filter; taxonomy embeddings cached to disk |
| `prompt_builder.py` | Prompt construction | Article dict → CoT prompt with rubric, anchors, and calibration rules |
| `classifier.py` | OpenAI interface | Prompt → validated Pydantic object; retry on rate limits |
| `scoring.py` | Deterministic math | LLM output or fallback → `risk_score` (float), `confidence` (str), `processing_status` (str) |
| `cost_evaluation.py` | Optional utilities | `tiktoken`-based cost estimation, random evaluation sample |

---

## Stage 1: Triage Layer

### Keyword Filter

Defined in `config.py → EVENT_TAXONOMY`. Each of the five event categories holds a list of keyword strings. Matching uses `re.search` with `\b` word-boundary anchors and case-insensitive comparison prevents partial matches (e.g., `"mine"` does not match `"undermine"`).

An article passes if any keyword from any category appears in its content. The matched keywords are forwarded as `keywords_detected`.

**Five categories:**
1. Hormuz Closure
2. Kharg/Khark Attack or Seizure
3. Critical Gulf Infrastructure Attacks
4. Direct Entry of Saudi/UAE/Coalition Forces
5. Red Sea / Bab el-Mandeb Escalation

### Embedding Filter

Taxonomy descriptions are embedded using `text-embedding-3-small`. On first run, all 8 embeddings (5 positive + 3 negative) are computed and saved to `data/.taxonomy_cache.pkl`. Every subsequent run loads from cache with no API calls at startup.

Per article:
- Article is embedded via `text-embedding-3-small`
- Cosine similarity computed against all 5 positive centroids and 3 negative centroids
- `max_pos` = highest positive similarity, `max_neg` = highest negative similarity
- Rejected if: `max_neg > max_pos` AND `max_neg > NEGATIVE_SIM_THRESHOLD`
- Rejected if: `max_pos < TRIAGE_POSITIVE_THRESHOLD`

Both thresholds are defined in `config.py` — tunable without touching `triage.py`.

---

## Stage 2: Classification Layer

### Prompt Construction (`prompt_builder.py`)

Each article generates an isolated prompt. The system persona is in the `system` message (not the user prompt), which is weighted differently by the model and produces more consistent role adherence.

User prompt contains:
- **Scoring rubric** with explicit `0.0` and `1.0` anchors on all four dimensions (physical, escalation, evidence, signal)
- **Calibration rules** with explicit guardrails preventing score inflation on pure rhetoric or diplomatic statements
- **Chain-of-Thought instruction** with `step_by_step_analysis` must be written before any score is committed
- **Article content** truncated to exactly `MAX_CONTENT_TOKENS` (700) tokens via `tiktoken`

### API Call (`classifier.py`)

- Model: `gpt-4o-mini` (from `config.py → MODEL_NAME`)
- `temperature=0.0` — maximum determinism
- `max_tokens=350` — caps output cost
- Pydantic schema with `ge=0.0, le=1.0` on all score fields — invalid ranges rejected at validation level
- Retry logic: `RateLimitError` → wait `2^attempt` seconds (1s, 2s, 4s), max 3 attempts
- `APIConnectionError` → retry once after 1s
- All other exceptions → return `None` immediately, fallback path activates

### Structured Output Fields

```
step_by_step_analysis  → str
physical_score         → float  [0.00–1.00]
escalation_score       → float  [0.00–1.00]
evidence_score         → float  [0.00–1.00]
signal_score           → float  [0.00–1.00]
event_labels           → list[str]
rationale              → str
```

---

## Post-Processing Layer

All math runs in `scoring.py` — no further API calls.

**Risk score (SPEC formula):**
```
risk_score = round(clip(0.45 * physical_score + 0.35 * escalation_score + 0.20 * evidence_score), 2)
```

**Confidence (SPEC formula):**
```
confidence_score = 0.5 * evidence_score + 0.3 * signal_score + 0.2 * model_score

confidence_score >= 0.70  →  "high"
confidence_score >= 0.40  →  "medium"
confidence_score <  0.40  →  "low"
```

`model_score` is derived deterministically from `event_labels` count and rationale quality not returned by the LLM.

**Fallback path** (when `classify_article()` returns `None`):
```python
llm_data = calculate_fallback_scores(detected_keywords)
processing_status = 'fallback'
```
Produces heuristic scores based on keyword severity. Higher-severity keywords (e.g., `"tanker attack"`, `"drone strike"`) raise physical and escalation scores above baseline.

---

## Concurrency Model

`main.py` uses `ThreadPoolExecutor(max_workers=10)` to process up to 10 articles concurrently. Each article is an isolated API call with no shared state between threads.

Results are collected into a position-indexed dict (`{original_index: result}`) as threads complete. Final ordering is reconstructed in O(n) by reading the dict in key order — no linear scan or O(n²) sort.

```python
# Submission: store original index as dict value
future_to_idx = {executor.submit(process_single_article, idx, row): idx
                 for idx, row in enumerate(articles)}

# Collection: slot results by original position
indexed_results = {}
for future in as_completed(future_to_idx):
    indexed_results[future_to_idx[future]] = future.result()

# Reconstruct in order — O(n)
results = [indexed_results[i] for i in range(len(articles))]
```

---

## External Dependencies

| Service | Usage | Configured via |
|---|---|---|
| OpenAI `gpt-4o-mini` | Stage 2 classification | `config.py → MODEL_NAME` |
| OpenAI `text-embedding-3-small` | Stage 1 embedding filter | `config.py → EMBEDDING_MODEL` |

All credentials loaded from `.env` via `python-dotenv`. Missing key raises `EnvironmentError` at startup.

---

## Error Handling

| Failure Mode | Strategy |
|---|---|
| Missing `OPENAI_API_KEY` | `EnvironmentError` raised at startup in `config.py` — pipeline never starts |
| Missing or wrong input CSV columns | `ValueError` raised in `io_csv.py` before triage begins |
| OpenAI `RateLimitError` | Exponential backoff: 1s → 2s → 4s, max 3 retries |
| OpenAI `APIConnectionError` | Retry once after 1s, then return `None` |
| All other API exceptions | Return `None` immediately, activate fallback scorer |
| Empty triage output | Pipeline completes with empty output CSV, warning logged |
| Embedding API failure in triage | Falls back to keyword-only result, warning printed |