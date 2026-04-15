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
- The optional embedding cache (avoids recomputing embeddings on re-runs)
- The final `outputs/result.csv`

---

## Pipeline Diagram

```text
┌──────────────────────────────────────────────────────────┐
│                        INPUT                             │
│                  data/newsdata.csv                       │
└────────────────────────┬─────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────┐
│              STAGE 1 — TRIAGE  (triage_advanced.py)      │
│                                                          │
│  Step 1: Keyword Filter (deterministic)                  │
│  └─ Match article content against taxonomy keywords.     │
│                                                          │
│  Step 2: Negative Semantic Filter (Embedding)            │
│  └─ Embed passing articles via text-embedding-3-small.   │
│  └─ Compare cosine similarity to negative centroids      │
│     (e.g., local politics, historical documentaries).    │
│  └─ REJECT if it aligns closer to noise than an attack.  │
│                                                          │
└────────────────────────┬─────────────────────────────────┘
                         │  ~15–30% of input articles
                         ▼
┌──────────────────────────────────────────────────────────┐
│           STAGE 2 — CLASSIFICATION (classifier.py)       │
│                                                          │
│  prompt_builder.py                                       │
│  └─ Build Chain-of-Thought prompt with scoring rubric.   │
│  └─ INVERTED PYRAMID TRUNCATION: Max 3,000 chars.        │
│                                                          │
│  classifier.py (ASYNC EXECUTION)                         │
│  └─ Call gpt-4o-mini via strict Pydantic parsing.        │
│  └─ ThreadPoolExecutor processes multiple articles       │
│     concurrently, 1 article per API call.                │
│                                                          │
└────────────────────────┬─────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────┐
│         POST-PROCESSING — SCORING  (scoring.py)          │
│                                                          │
│  risk_score = 0.45(phys) + 0.35(esc) + 0.20(evid)        │
│  confidence = 0.5(evid) + 0.3(sig) + 0.2(model)          │
└────────────────────────┬─────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────┐
│                       OUTPUT                             │
│                  outputs/result.csv                      │
└──────────────────────────────────────────────────────────┘
```

---

## Component Responsibilities

| File | Role | Key Inputs / Outputs |
|---|---|---|
| `main.py` | Orchestrator and CLI entry point | Reads args, calls triage → classify → score → write |
| `config.py` | Single source of truth | Keyword taxonomy, model names, weights, thresholds |
| `io_csv.py` | I/O | CSV load → DataFrame; enriched records → CSV |
| `triage.py` | Stage 1 filter | DataFrame in → filtered DataFrame out |
| `prompt_builder.py` | Prompt construction | Article dict → formatted prompt string |
| `classifier.py` | OpenAI interface | Prompt → validated `ClassifierOutput` Pydantic object |
| `scoring.py` | Deterministic math | `ClassifierOutput` → `risk_score` (float), `confidence` (str) |
| `cost_evaluation.py` | Optional utilities | Cost estimation, evaluation sample generation |

---

## Stage 1: Triage Layer

### Keyword Filter

Defined entirely in `config.py` under `KEYWORD_TAXONOMY`. Each of the five event categories holds a list of keyword strings. Matching is case-insensitive substring search against `content`.

An article passes if any keyword from any category appears in its content. The matched keywords are forwarded as `keywords_detected`.

**Five categories checked:**
1. Hormuz Closure
2. Kharg/Khark Attack or Seizure
3. Critical Gulf Infrastructure Attacks
4. Direct Entry of Saudi/UAE/Coalition Forces
5. Red Sea / Bab el-Mandeb Escalation

### Embedding Filter (Optional Enhancement)

If enabled via `config.py → USE_EMBEDDING_FILTER = True`:

- Articles passing keyword matching are embedded using `text-embedding-3-small`
- Each embedding is compared (cosine similarity) against pre-computed **negative taxonomy centroids**:
  - `HISTORICAL_DOCUMENTARY`
  - `DOMESTIC_ELECTIONS`
  - `STOCK_MARKET_NOISE`
- Articles exceeding `NEGATIVE_SIM_THRESHOLD` (default: `0.82`) on any centroid class are rejected
- Embeddings are cached to disk to avoid redundant API calls on re-runs

This step reduces false positives from articles that match keywords incidentally (e.g., a historical documentary mentioning the Strait of Hormuz).

---

## Stage 2: Classification Layer

### Prompt Construction (`prompt_builder.py`)

Each article generates an isolated prompt containing:
- **System role:** geopolitical risk analyst specialising in Middle East energy security
- **Scoring rubric:** explicit 0.0–1.0 definitions for each scoring dimension
- **Chain-of-Thought instructions:** step-by-step reasoning before committing to scores
- **Article content:** truncated to 3,000 characters
- **Output schema description:** field names and types mirroring `ClassifierOutput`

### API Call (`classifier.py`)

- Model: `gpt-4o-mini` (configurable in `config.py`)
- Mode: OpenAI Responses API with `strict=True` JSON Structured Outputs
- Schema enforced via Pydantic `ClassifierOutput` model
- One article per API call — strict isolation prevents context bleed between articles

### Structured Output Fields Returned by LLM

```
event_labels       → list[str]   (subset of taxonomy category names)
physical_score     → float       [0.00–1.00]
escalation_score   → float       [0.00–1.00]
evidence_score     → float       [0.00–1.00]
signal_score       → float       [0.00–1.00]
model_score        → float       [0.00–1.00]
rationale          → str
keywords_detected  → list[str]
```

---

<!-- ## Stage 3:  -->

## Post-Processing Layer

All math is deterministic and runs in `scoring.py` with no further API calls.

**Risk score:**
```
risk_score = round(clip(0.45 * physical_score + 0.35 * escalation_score + 0.20 * evidence_score), 2)
```

**Confidence:**
```
confidence_score = 0.5 * evidence_score + 0.3 * signal_score + 0.2 * model_score

confidence_score >= 0.70  →  "high"
confidence_score >= 0.40  →  "medium"
confidence_score <  0.40  →  "low"
```

Only `risk_score` and `confidence` (categorical) are written to the output CSV. All component scores exist only in the intermediate `ClassifierOutput` object.

---

## Concurrency Model

`main.py` processes articles sequentially by default. For larger datasets, `ThreadPoolExecutor` can parallelise Stage 2 API calls. Strict per-article prompt isolation means no shared state exists between concurrent workers.

---

## External Dependencies

| Service | Usage | Configured in |
|---|---|---|
| OpenAI `gpt-4o-mini` | Stage 2 classification | `config.py → MODEL_NAME` |
| OpenAI `text-embedding-3-small` | Optional Stage 1 embedding filter | `config.py → EMBEDDING_MODEL` |

All credentials loaded from `.env` via `python-dotenv`.

---

## Error Handling

| Failure Mode | Strategy |
|---|---|
| OpenAI API timeout / rate limit | Retry with exponential backoff (max 3 attempts) |
| Pydantic validation failure | Log warning, skip article, continue pipeline |
| Missing input CSV | Raise `FileNotFoundError` at startup |
| Malformed CSV row | Skip row, log warning, continue |
| Empty triage output | Log warning, exit gracefully with empty output CSV |
