# DATA_MODEL.md — Geopolitical Risk Assessment Pipeline

## Table of Contents

- [Overview](#overview)
- [Input Schema](#input-schema)
- [Output Schema](#output-schema)
- [Intermediate Data Model — ClassifierOutput](#intermediate-data-model--classifieroutput)
- [Event Taxonomy Reference](#event-taxonomy-reference)
- [Score Definitions](#score-definitions)
- [Confidence Mapping](#confidence-mapping)
- [Risk Score Interpretation Bands](#risk-score-interpretation-bands)
- [Data Flow Summary](#data-flow-summary)

---

## Overview

The pipeline operates on a single CSV file and produces a single enriched CSV file. Between those two states, articles are represented as Python dicts and Pydantic objects. No database or intermediate file storage is used except the taxonomy embedding cache (`data/.taxonomy_cache.pkl`).

---

## Input Schema

**File:** `data/newsdata.csv`
**Format:** UTF-8 CSV, header row required

| Column | Type | Required | Description |
|---|---|---|---|
| `pubDate` | string (datetime) | Yes | Publication timestamp. Format: `YYYY-MM-DD HH:MM:SS` or ISO 8601. |
| `link` | string (URL) | Yes | Canonical URL of the article. |
| `content` | string | Yes | Full article body text in English. |
| `source_id` | string | Yes | Identifier for the originating news source. |

**Validation rules:**
- All four columns must be present — `io_csv.py` raises `ValueError` at load time if any are missing
- `content` must be non-null and non-empty for an article to enter triage
- No assumption is made about row ordering

---

## Output Schema

**File:** `outputs/result.csv`
**Format:** UTF-8 CSV. Contains all input columns plus the six enriched fields below.

### Passthrough columns (unchanged from input)

| Column | Type |
|---|---|
| `pubDate` | string |
| `link` | string |
| `content` | string |
| `source_id` | string |

### Enriched columns (added by pipeline)

| Column | Type | Range / Values | Description |
|---|---|---|---|
| `event_labels` | string | See taxonomy | Comma-separated detected event category names. Empty if no event confirmed. |
| `risk_score` | float | `0.00 – 1.00` | Composite macroeconomic risk score, rounded to 2 decimal places. |
| `confidence` | string | `low`, `medium`, `high` | Reliability of the classification, not event severity. |
| `rationale` | string | Free text | LLM-generated justification (1 sentence). |
| `keywords_detected` | string | Taxonomy keywords | Comma-separated keywords from `EVENT_TAXONOMY` matched in the article. |
| `processing_status` | string | `success`, `fallback`, `triage_rejected` | Indicates how the row was scored. See interpretation below. |

### `processing_status` Interpretation

| Value | Meaning |
|---|---|
| `success` | Article passed triage and was scored by the LLM. Scores are fully reliable. |
| `fallback` | Article passed triage but the API failed. Scores are keyword heuristics so treat with caution. |
| `triage_rejected` | Article did not pass the triage filter. `risk_score = 0.0` is intentional, not a failure. |

### Example output row

```csv
pubDate,link,content,source_id,event_labels,risk_score,confidence,rationale,keywords_detected,processing_status
2024-10-15 08:30:00,https://example.com/article,Iran threatened...,reuters,Hormuz Closure,0.61,high,"Confirmed naval deployment near Strait of Hormuz with documented insurance spike.","strait of hormuz, war risk insurance, irgc navy",success
```

---

## Intermediate Data Model — ClassifierOutput

`ClassifierOutput` is a Pydantic model defined in `classifier.py`. It is the validated structured output returned by the LLM before deterministic post-processing.

```python
class GeopoliticalRiskAssessment(BaseModel):
    step_by_step_analysis: str = Field(
        description="Briefly debate the facts of the article against the rubric."
    )
    physical_score: float = Field(
        ge=0.0, le=1.0,
        description="Score between 0.0 and 1.0."
    )
    escalation_score: float = Field(
        ge=0.0, le=1.0,
        description="Score between 0.0 and 1.0."
    )
    evidence_score: float = Field(
        ge=0.0, le=1.0,
        description="Score between 0.0 and 1.0."
    )
    signal_score: float = Field(
        ge=0.0, le=1.0,
        description="Score between 0.0 and 1.0."
    )
    event_labels: List[str] = Field(
        description="List of detected event categories from the taxonomy."
    )
    rationale: str = Field(
        description="A professional 1-sentence final justification."
    )
```

**Key constraints:**
- All score fields: `ge=0.0, le=1.0` — values outside this range are rejected by Pydantic at validation time, not silently accepted
- `event_labels`: values must match taxonomy category names exactly as defined in `config.py`
- `step_by_step_analysis` is written first (Chain-of-Thought) before the model commits to scores

`ClassifierOutput` is an internal object consumed by `scoring.py`. It is not persisted to disk.

**Note:** `model_score` is not returned by the LLM. It is computed deterministically in `scoring.py` from `event_labels` count and rationale quality, keeping LLM output clean and the confidence formula transparent.

---

## Event Taxonomy Reference

Defined in `config.py → EVENT_TAXONOMY`. Used in both triage (keyword matching) and classification (label names).

### 1. Hormuz Closure

| Keyword |
|---|
| hormuz |
| strait of hormuz |
| mine |
| naval mine |
| mining |
| tanker attack |
| vessel attack |
| ship attack |
| shipping halt |
| transit halt |
| blockade |
| war risk insurance |
| insurance spike |
| naval incident |
| irgc navy |

### 2. Kharg/Khark Attack or Seizure

| Keyword |
|---|
| kharg |
| khark |
| oil terminal |
| export terminal |
| landing |
| amphibious landing |
| seize |
| takeover |
| capture |
| export halt |
| loading stop |
| offshore facilities |
| loading jetty |

### 3. Critical Gulf Infrastructure Attacks

| Keyword |
|---|
| refinery |
| oil facility |
| processing plant |
| gas plant |
| lng terminal |
| desalination |
| water plant |
| pipeline |
| pumping station |
| saudi |
| uae |
| fujairah |
| abqaiq |
| ras tanura |
| drone strike |
| missile strike |
| sabotage |

### 4. Direct Entry of Saudi/UAE/Coalition Forces

| Keyword |
|---|
| coalition |
| multinational force |
| ground forces |
| troop deployment |
| amphibious operation |
| saudi intervention |
| uae intervention |
| joint operation |
| allied response |
| escalation |
| regional war |

### 5. Red Sea / Bab el-Mandeb Escalation

| Keyword |
|---|
| houthis |
| houthi attacks |
| red sea |
| bab el-mandeb |
| merchant vessels |
| cargo ships |
| shipping reroute |
| diversion |
| naval escort |
| convoy |

---

## Score Definitions

All scores are continuous floats in `[0.00, 1.00]`. The LLM produces physical, escalation, evidence, and signal scores. `model_score` is computed deterministically in `scoring.py`.

### Risk Component Scores

| Score | Weight | 0.0 Anchor | 1.0 Anchor |
|---|---|---|---|
| `physical_score` | 0.45 | Pure rhetoric, threats, or diplomatic warnings with no physical action | Total destruction or confirmed blockade of critical assets |
| `escalation_score` | 0.35 | Routine local conflict, isolated bilateral exchange | Major regional war involving multiple state actors (Saudi, UAE, Iran, US) |
| `evidence_score` | 0.20 | Rumour, unverified social media, or highly speculative opinion piece | Confirmed multi-source factual reporting with named sources |

### Confidence Component Scores

| Score | Weight | Description |
|---|---|---|
| `evidence_score` | 0.50 | Reused directly from risk scoring |
| `signal_score` | 0.30 | Internal article consistency. `0.0` = contradictions, mixed signals, unclear if event occurred. `1.0` = multiple sentences consistently support the same event, no contradictions, event clearly occurred. |
| `model_score` | 0.20 | Derived from `event_labels` count and rationale quality. Single precise label with specific factual language → high. Three or more labels or vague rationale → low. |

---

## Confidence Mapping

```
confidence_score = 0.5 * evidence_score + 0.3 * signal_score + 0.2 * model_score

confidence_score >= 0.70  →  "high"
confidence_score >= 0.40  →  "medium"
confidence_score <  0.40  →  "low"
```

---

## Risk Score Interpretation Bands

```
risk_score = 0.45 * physical_score + 0.35 * escalation_score + 0.20 * evidence_score
             (rounded to 2 d.p., clipped to [0.00, 1.00])
```

| Range | Band | Interpretation |
|---|---|---|
| 0.00 – 0.19 | Background noise | Political commentary, no actionable signal |
| 0.20 – 0.39 | Relevant tension | Noteworthy but no clear macroeconomic shock |
| 0.40 – 0.59 | Credible signal | Escalation worth monitoring |
| 0.60 – 0.79 | High macro-risk | Material geopolitical event |
| 0.80 – 1.00 | Severe shock | Confirmed major disruption or critical escalation |

---

## Data Flow Summary

```
newsdata.csv
    │
    │  io_csv.py → validate required columns → load as list of dicts
    │
    ▼
List of article dicts [pubDate, link, content, source_id]
    │
    │  triage.py
    │    Layer 1: keyword regex filter (zero API cost)
    │    Layer 2: embedding similarity filter
    │             (taxonomy centroids from disk cache or computed once)
    │
    ▼
Filtered list (subset of articles that passed triage)
    │
    │  main.py — ThreadPoolExecutor (up to 10 concurrent threads)
    │
    │  Per article:
    │    tiktoken → truncate to 700 tokens exactly
    │    prompt_builder.py → build CoT prompt with rubric + calibration rules
    │    classifier.py → call gpt-4o-mini with retry logic
    │                 → return GeopoliticalRiskAssessment (Pydantic) or None
    │    if None → calculate_fallback_scores(keywords) → processing_status='fallback'
    │    scoring.py → risk_score, confidence, processing_status
    │
    ▼
indexed_results dict {original_index: enriched_row}
    │
    │  Reconstruct in original order O(n):
    │  results = [indexed_results[i] for i in range(len(articles))]
    │
    ▼
List of enriched dicts [all input fields + 6 output fields]
    │
    │  io_csv.py → write_csv()
    │
    ▼
outputs/result.csv
```