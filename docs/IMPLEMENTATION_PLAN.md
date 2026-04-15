# IMPLEMENTATION_PLAN.md — Geopolitical Risk Assessment Pipeline

## Table of Contents

- [Objective](#objective)
- [Implementation Phases](#implementation-phases)
  - [Phase 1: Config and I/O Foundation](#phase-1-config-and-io-foundation)
  - [Phase 2: Optimization](#phase-2-optimization)
    - [Stage 1 (Semantic Triage)](#stage-1-semantic-triage)
    - [Stage 2 (LLM Precision)](#stage-2-llm-precision)
  - [Phase 3: Scaling & Cost Reduction (Advanced Features)](#phase-3-scaling--cost-reduction)
- [Technical Decisions](#technical-decisions)
- [Known Trade-offs and Limitations](#known-trade-offs-and-limitations)


---

## Objective

Translate the SPEC.md specification into a working, clean, and well-structured Python pipeline that:
- Accepts a CSV of news articles via CLI
- Identifies geopolitical escalation events across five defined categories
- Produces structured risk scores and confidence ratings
- Prioritises precision over recall throughout


## Implementation Phases

---

### Phase 1: Config and I/O Foundation

**Goal:** Establish the deterministic rules and standard I/O loops to fulfill the baseline specification.

#### Tasks:

1. Set up the environment and API connection tests.
2. Parse the input CSV (io_csv.py).
3. Implement a rule-based Regex Triage using the 5 predefined Geopolitical Event Taxonomy categories.
4. Implement the exact risk_score and confidence mathematical formulas in scoring.py.

---

### Phase 2: Optimization

### Stage 1: Semantic Triage

**Goal:** Reduce false positives and API costs before the expensive LLM step.

#### Tasks:

1. Integrate the OpenAI text-embedding-3-small model into triage.py to measure article context beyond simple regex.
2. Implement a "Negative Taxonomy" (Anti-Filter). If an article mathematically aligns closer with historical documentaries, domestic politics, or stock market noise than with a kinetic attack, it is instantly blocked.
---

### Stage 2 LLM Precision

**Goal:** Eliminate hallucinations and enforce rigorous schema structure.

#### Tasks:

1. Upgrade the LLM prompt to "Chain-of-Thought" (CoT) architecture, requiring the LLM to output a step_by_step_analysis string prior to generating scores.
2. Implement OpenAI's Structured Outputs (strict=True) using the pydantic Python library. This creates a data contract that guarantees the LLM returns exact JSON keys and valid float data types, eliminating parsing crashes.

---

### Phase 3: Scaling & Cost Reduction

**Goal:** Speed up processing and drastically cut token costs.

### Tasks:

1. Inverted Pyramid Truncation: Pass only the first 3,000 characters of the article text to the LLM. This takes advantage of journalistic structure, cutting API costs by ~55% and increasing accuracy by removing historical filler text found at the bottom of long articles.
2. Max Token Budgeting: Apply max_tokens=350 to the completion call to strictly cap output billing and enforce concise rationales.
3. Asynchronous Architecture: Refactor main.py to use ThreadPoolExecutor, processing multiple articles concurrently. (Note: Prompt batching was explicitly rejected to prioritize absolute precision and avoid cross-article context bleed).

---

## Technical Decisions

| Decision | Rationale |
|---|---|
| `gpt-4o-mini` as default model | Balances cost and quality for structured classification; easily swapped in `config.py` |
| Asynchronous Isolated Calls | Eliminates context bleed; precision over throughput |
| Pydantic Structured Outputs with `strict=True` | Eliminates JSON parsing fragility; crashes are avoided at the schema level |
| 3,000-char content truncation | News follows inverted pyramid, critical facts appear early; reduces token cost without accuracy loss |
| Negative Semantic Filtering | Highly effective at catching dense financial/political articles that bypass standard keyword checks |

---

## Known Trade-offs and Limitations

| Trade-off | Impact |
|---|---|
| Rejection of Prompt Batching | Slight increase in redundant system-prompt token costs, traded for a guarantee of maximum individual article precision. |
| Geographic Blurring | The LLM occasionally struggles with rigid geographic boundaries when an event closely matches a neighboring category (e.g., Oman infrastructure vs. UAE infrastructure). |
| 3,000-char truncation loses article tail | Risk of missing confirmatory detail buried in later paragraphs |
| Cost scales with triage pass-rate | High-noise datasets with many keyword matches increase cost disproportionately |
