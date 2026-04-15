# 🌍 Geopolitical Risk Assessment Pipeline

A high-precision, asynchronous Python pipeline that processes news articles to detect geopolitical escalation events involving **Iran, the US, and Israel** distinguishing real macroeconomic shocks from background political noise.

---

## Table of Contents

- [Overview & Approach](#overview--approach)
- [Folder Structure](#folder-structure)
- [Installation & Configuration](#installation--configuration)
- [How to Run](#how-to-run)
- [Optional Enhancements](#optional-enhancements)
- [Assumptions & Limitations](#assumptions--limitations)
---

## Overview & Approach

The pipeline runs in two sequential stages:

**Stage 1 — Triage (Deterministic)**
A rule-based keyword filter screens all articles against five predefined event categories. Only articles matching at least one keyword set advance to Stage 2. An optional embedding-based negative filter further reduces false positives by rejecting articles that semantically resemble noise classes (documentaries, domestic elections, financial market commentary).

**Stage 2 — LLM Classification (OpenAI)**
Triaged articles are sent to `gpt-4o-mini` via the OpenAI Responses API with Structured Outputs enforced by a Pydantic schema. The model produces event labels, three normalized component scores, a rationale, and detected keywords. A deterministic post-processing step computes the final `risk_score` and categorical `confidence` from those components.

The system prioritises **high precision** — ambiguous articles default to conservative scores.

---

## Folder Structure

```
geopolitical-risk-pipeline/
│
├── main.py                 # Async execution pipeline (Triage → Classify → Export)
├── config.py               # Centralized constants, taxonomy, and model 
├── io_csv.py               # Standardized CSV read/write utilities
├── triage.py               # Phase 1: Hybrid keyword + embedding filter
├── prompt_builder.py       # Chain-of-Thought prompt construction
├── classifier.py           # Phase 2: OpenAI API calls with Structured 
├── scoring.py              # Risk and Confidence score computation
├── cost_evaluation.py      # Phase 3: Standalone cost + evaluation report
├── data/
│   └── newsdata_oil.csv    # Raw input dataset
├── docs/
│   └── ARCHITECTURE.md    
|   └── DATA_MODEL.md  
|   └── IMPLEMENTATION_PLAN.md  
├── outputs/
│   └── result.csv          # Final enriched output with risk scores
├── requirements.txt        # list of libraries to install
├── .env                    # API key (not committed — see Configuration)
└── README.md
```

---

## Installation & Configuration

Requires **Python 3.10+**, ***conda(recommended)***

```bash 
python -m ensurepip --upgrade
or
conda install pip
```
Use requirements.txt to install specific versions

```bash
pip install openai pydantic pandas python-dotenv tiktoken
or
pip install -r requirements.txt
```

---

Create a `.env` file in the project root:

```env
OPENAI_API_KEY=sk-your-api-key-here
```

> Add `.env` to `.gitignore` — never commit API keys.

All model names, score weights, thresholds, and keyword taxonomy are defined in `config.py`.

---

## How to Run

Run the Full Pipeline:

```bash
python main.py --input data/newsdata.csv --output outputs/result.csv
```

Generate Cost & Evaluation Report:

```bash
python python cost_evaluation.py
```

The pipeline will:
1. Load and validate the input CSV
2. Run triage filter to candidate articles
3. Classify each candidate via OpenAI
4. Compute risk scores and confidence
5. Write the enriched CSV to the output path

---

## Optional Enhancements

| Enhancement | Implementation |
|---|---|
| **Triage Improvement** | Embedding-based negative filter using `text-embedding-3-small` against noise centroids |
| **Prompt Design Iteration** | Chain-of-Thought rubric with step-by-step scoring instructions per dimension |
| **Evaluation Sample** | Manual test set of 5–10 labelled articles in `cost_evaluation.py` with precision/recall notes |
| **Cost Awareness** | Dynamic token counting using tiktoken to analyze the actual dataset and per-100-article cost estimation in `cost_evaluation.py` |

---

## Assumptions & Limitations

**Assumptions:**
- Input CSV is well-formed and uses the fixed schema defined in the spec
- All articles are in English
- `gpt-4o-mini` is the target model; switching models requires updating `config.py` only
- Article content is truncated to 3,000 characters before LLM submission (inverted pyramid — key facts appear early)

**Limitations:**
- Keyword triage may miss paraphrased events not matching exact terminology
- LLM scores carry inherent non-determinism; identical articles may produce marginally different scores across runs
- No streaming or real-time capability, batch processing only
- Cost scales linearly with the number of articles passing triage; embedding caching mitigates repeated runs
