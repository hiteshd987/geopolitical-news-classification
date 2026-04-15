# DATA_MODEL.md — Geopolitical Risk Assessment Pipeline

## Table of Contents

- [Overview](#overview)
- [Input Schema](#input-schema)
- [Output Schema](#output-schema)
- [Intermediate Data Model — ClassifierOutput](#intermediate-data-model)
- [Event Taxonomy Reference](#event-taxonomy-reference)
- [Score Definitions](#score-definitions)
- [Confidence Mapping](#confidence-mapping)
- [Risk Score Interpretation Bands](#risk-score-interpretation-bands)
- [Data Flow Summary](#data-flow-summary)

---

## Overview

The pipeline operates on a single CSV file and produces a single enriched CSV file. Between those two states, articles are represented as Python dicts and Pydantic objects. No database or intermediate file storage is used (except the optional embedding cache).

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
- `content` must be non-null and non-empty for an article to enter triage
- Rows with missing `content` are skipped with a logged warning
- No assumption is made about row ordering

---

## Output Schema

**File:** `outputs/result.csv`
**Format:** UTF-8 CSV. Contains all input columns plus the five enriched fields below.

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
| `event_labels` | JSON string (list) | See taxonomy | Detected event category names. Empty list `[]` if no event confirmed. |
| `risk_score` | float | `0.00 – 1.00` | Composite macroeconomic risk score, rounded to 2 decimal places. |
| `confidence` | string | `low`, `medium`, `high` | Reliability of the classification, not event severity. |
| `rationale` | string | Free text | Short LLM-generated justification (1–3 sentences). |
| `keywords_detected` | JSON string (list) | Taxonomy keywords | Keywords from `KEYWORD_TAXONOMY` found in the article. |

### Example output row

```csv
pubDate,link,content,source_id,event_labels,risk_score,confidence,rationale,keywords_detected
2024-10-15 08:30:00,https://example.com/article,Iran threatened...,reuters,"[""Hormuz Closure""]",0.61,high,"Article reports confirmed naval deployment near Strait of Hormuz with operational impact on shipping insurance rates. Multiple corroborating sources cited.","[""Strait of Hormuz"", ""war risk insurance"", ""IRGC navy""]"
```

### Articles that do not pass triage

Articles rejected by the triage stage are **not written to the output CSV**. The output contains only triaged and classified rows. This is by design the output schema is enriched-articles-only.

> If a full passthrough (including rejected articles with null enriched fields) is required, this can be enabled via `config.py → INCLUDE_REJECTED = True`.

---

## Intermediate Data Model

`ClassifierOutput` is a Pydantic model defined in `classifier.py`. It represents the raw structured output returned by the LLM before deterministic post-processing.

```python
class ClassifierOutput(BaseModel):
    event_labels: list[str]        # subset of taxonomy category names
    physical_score: float          # [0.00, 1.00]
    escalation_score: float        # [0.00, 1.00]
    evidence_score: float          # [0.00, 1.00]
    signal_score: float            # [0.00, 1.00]
    model_score: float             # [0.00, 1.00]
    rationale: str                 # short justification
    keywords_detected: list[str]   # matched taxonomy keywords
```

**Validation constraints (enforced by Pydantic):**
- All score fields: `ge=0.0`, `le=1.0`
- `event_labels`: each value must be a valid taxonomy category name or empty list
- `rationale`: non-empty string
- `keywords_detected`: may be empty list if no keywords confirmed by LLM

`ClassifierOutput` is an internal object. It is consumed by `scoring.py` and is not persisted to disk.

---

## Event Taxonomy Reference

Defined in `config.py → KEYWORD_TAXONOMY`. Used in both triage (keyword matching) and classification (label names).

### 1. Hormuz Closure

| Keyword |
|---|
| Hormuz |
| Strait of Hormuz |
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
| IRGC navy |

### 2. Kharg/Khark Attack or Seizure

| Keyword |
|---|
| Kharg |
| Khark |
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
| LNG terminal |
| desalination |
| water plant |
| pipeline |
| pumping station |
| Saudi |
| UAE |
| Fujairah |
| Abqaiq |
| Ras Tanura |
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
| Saudi intervention |
| UAE intervention |
| joint operation |
| allied response |
| escalation |
| regional war |

### 5. Red Sea / Bab el-Mandeb Escalation

| Keyword |
|---|
| Houthis |
| Houthi attacks |
| Red Sea |
| Bab el-Mandeb |
| merchant vessels |
| cargo ships |
| shipping reroute |
| diversion |
| naval escort |
| convoy |

---

## Score Definitions

All scores are continuous floats in `[0.00, 1.00]`, produced by the LLM and used in deterministic post-processing.

### Risk Component Scores

| Score | Description | High Signal Examples | Low Signal Examples |
|---|---|---|---|
| `physical_score` | Real or imminent disruption to energy flows, shipping, or infrastructure | Confirmed shipping halt, mine deployment, tanker attack with operational impact, export terminal seizure | Political statement with no action, diplomatic warning |
| `escalation_score` | Conflict expanding to broader regional or multinational confrontation | Direct Saudi/UAE entry, coalition formation, spread to Red Sea / Bab el-Mandeb | Isolated bilateral exchange, verbal sparring |
| `evidence_score` | Factual reporting quality vs. rhetoric or speculation | Reported facts, named sources, operational consequences cited | Anonymous sources only, opinion piece, hypothetical scenario |

### Confidence Component Scores

| Score | Description |
|---|---|
| `evidence_score` | Reused directly from risk scoring |
| `signal_score` | Internal article consistency — multiple sentences supporting same event, no contradictions |
| `model_score` | LLM classification precision — fewer labels with strong rationale → higher score |

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

| Range | Band Label | Interpretation |
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
    │  io_csv.py → read as pandas DataFrame
    │
    ▼
DataFrame [pubDate, link, content, source_id]
    │
    │  triage.py → keyword filter → (optional) embedding filter
    │
    ▼
Filtered DataFrame (subset of rows)
    │
    │  For each row:
    │    prompt_builder.py → str (prompt)
    │    classifier.py     → ClassifierOutput (Pydantic)
    │    scoring.py        → risk_score (float), confidence (str)
    │
    ▼
List of enriched dicts [all input fields + 5 output fields]
    │
    │  io_csv.py → write as CSV
    │
    ▼
outputs/result.csv
```
