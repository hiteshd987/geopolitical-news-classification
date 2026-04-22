# 🌍 Geopolitical Risk Assessment Pipeline

A high-precision, asynchronous Python pipeline that processes news articles to detect geopolitical escalation events involving **Iran, the US, and Israel** distinguishing real macroeconomic shocks from background political noise.

---

## Table of Contents

- [Overview & Approach](#overview--approach)
- [Folder Structure](#folder-structure)
- [Installation & Configuration](#installation--configuration)
- [How to Run](#how-to-run)
- [Output Schema](#output-schema)
- [Optional Enhancements](#optional-enhancements)
- [Assumptions & Limitations](#assumptions--limitations)

---

## Overview & Approach

The pipeline runs in two sequential stages:

**Stage 1 — Triage (Deterministic)**
A rule-based keyword filter screens all articles against five predefined event categories. Only articles matching at least one keyword set advance to Stage 2. An embedding-based negative filter further reduces false positives by rejecting articles that semantically resemble noise classes (documentaries, domestic elections, financial market commentary). Taxonomy embeddings are cached to disk on first run — no repeated API calls on subsequent runs.

**Stage 2 — LLM Classification (OpenAI)**
Triaged articles are sent to `gpt-4o-mini` via the OpenAI API with Structured Outputs enforced by a Pydantic schema. Article content is truncated to exactly **700 tokens** using `tiktoken` before submission. The model produces event labels, four normalised component scores, a rationale, and detected keywords. A deterministic post-processing step computes the final `risk_score` and categorical `confidence` from those components. If the API fails, a keyword-based fallback scorer runs automatically and no article returns silent zeros.

The system prioritises **high precision** by keeping ambiguous articles default to conservative scores.

---

## Folder Structure

```
geopolitical-risk-pipeline/
│
├── main.py                 # Async execution pipeline (Triage → Classify → Export)
├── config.py               # Centralised constants, taxonomy, model config, thresholds
├── io_csv.py               # CSV read/write with column validation
├── triage.py               # Stage 1: Hybrid keyword + embedding filter with disk cache
├── prompt_builder.py       # Chain-of-Thought prompt with calibration rules
├── classifier.py           # Stage 2: OpenAI API calls with Structured Outputs + retry
├── scoring.py              # Risk and Confidence score computation + fallback
├── cost_evaluation.py      # Standalone cost + evaluation report
├── data/
│   └── newsdata_oil.csv    # Raw input dataset
├── docs/
│   ├── ARCHITECTURE.md
│   ├── DATA_MODEL.md
│   └── IMPLEMENTATION_PLAN.md
├── outputs/
│   └── result.csv          # Final enriched output with risk scores
├── requirements.txt        # Pinned dependencies
├── .env                    # API key (not committed — see Configuration)
└── README.md
```

---

## Installation & Configuration

Requires **Python 3.10+**, `conda` recommended

```bash
python -m ensurepip --upgrade
# or
conda install pip
```

Install dependencies:

```bash
pip install -r requirements.txt
# or manually:
pip install openai pydantic pandas python-dotenv tiktoken
```

Create a `.env` file in the project root:

```env
OPENAI_API_KEY=sk-your-api-key-here
```

> Add `.env` to `.gitignore` — never commit API keys. The pipeline raises an `EnvironmentError` immediately at startup if the key is missing, before any processing begins.

All model names, score weights, thresholds, and keyword taxonomy are defined in `config.py`:

| Constant | Default | Purpose |
|---|---|---|
| `MODEL_NAME` | `gpt-4o-mini` | LLM used for classification |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | Embedding model used in triage |
| `MAX_CONTENT_TOKENS` | `700` | Token cap applied to article before LLM submission |
| `NEGATIVE_SIM_THRESHOLD` | `0.30` | Cosine similarity threshold for noise rejection |
| `TRIAGE_POSITIVE_THRESHOLD` | `0.25` | Minimum positive similarity required to pass triage |

---

## How to Run

**Full pipeline:**

```bash
python main.py --input data/newsdata_oil.csv --output outputs/result.csv
```

**Cost and evaluation report:**

```bash
python cost_evaluation.py
```

The pipeline will:
1. Load and validate the input CSV which raises an error immediately if required columns are missing
2. Run triage with keyword filter, then optional negative embedding filter
3. Classify each passing article via OpenAI with automatic retry on rate limits
4. Fall back to keyword-based heuristic scoring if the API fails completely
5. Compute risk scores and confidence deterministically in `scoring.py`
6. Write the enriched CSV in original row order

---

## Output Schema

The output CSV contains all original input columns plus:

| Column | Type | Description |
|---|---|---|
| `event_labels` | string | Comma-separated detected event category names |
| `risk_score` | float [0.00–1.00] | Composite macroeconomic risk score |
| `confidence` | `low` / `medium` / `high` | Classification reliability |
| `rationale` | string | LLM justification for the scores |
| `keywords_detected` | string | Matched taxonomy keywords from triage |
| `processing_status` | string | `success`, `fallback`, or `triage_rejected` |

`processing_status` makes every row interpretable — you can immediately tell whether a `0.0` risk score means a genuinely irrelevant article (`triage_rejected`), a successfully scored low-risk article (`success`), or one where the API failed and keyword heuristics were used (`fallback`).

---

## Optional Enhancements

| Enhancement | Implementation |
|---|---|
| **Triage Improvement** | Negative embedding filter using `text-embedding-3-small` with cached taxonomy centroids — blocks documentaries, elections, and stock market noise that bypass keyword checks |
| **Prompt Design Iteration** | Chain-of-Thought rubric with explicit `0.0`/`1.0` anchors on all four score dimensions plus calibration rules preventing score inflation on pure rhetoric |
| **Evaluation Sample** | Random sample of 5 articles run through the full pipeline in `cost_evaluation.py` with scores printed for manual review |
| **Cost Awareness** | Exact token counting via `tiktoken` with before/after truncation cost comparison in `cost_evaluation.py` |

---

## Assumptions & Limitations

**Assumptions:**
- Input CSV is well-formed and uses the fixed schema (`pubDate`, `link`, `content`, `source_id`)
- All articles are in English
- `gpt-4o-mini` is the target model; switching models requires updating `config.py` only
- Article content is truncated to exactly **700 tokens** before LLM submission — the journalistic inverted pyramid means critical facts appear in the opening paragraphs

**Limitations:**
- Keyword triage may miss paraphrased events that do not match exact taxonomy terminology
- LLM scores carry inherent non-determinism; `temperature=0.0` minimises but does not eliminate variance across runs
- No streaming or real-time capability, batch processing only
- Cost scales linearly with the number of articles passing triage; taxonomy embedding caching mitigates cost on repeated runs
- Fallback scores are keyword heuristics only and treat rows with `processing_status = 'fallback'` with caution in downstream analysis