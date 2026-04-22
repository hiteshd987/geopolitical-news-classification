# IMPLEMENTATION_PLAN.md — Geopolitical Risk Assessment Pipeline

## Table of Contents

- [Objective](#objective)
- [Implementation Phases](#implementation-phases)
  - [Phase 1: Config and I/O Foundation](#phase-1-config-and-io-foundation)
  - [Phase 2: Optimisation](#phase-2-optimisation)
    - [Stage 1 — Semantic Triage](#stage-1--semantic-triage)
    - [Stage 2 — LLM Precision](#stage-2--llm-precision)
  - [Phase 3: Scaling and Cost Reduction](#phase-3-scaling-and-cost-reduction)
  - [Phase 4: Robustness and Correctness](#phase-4-robustness-and-correctness)
- [Technical Decisions](#technical-decisions)
- [Known Trade-offs and Limitations](#known-trade-offs-and-limitations)

---

## Objective

Translate the SPEC.md specification into a working, clean, and well-structured Python pipeline that:
- Accepts a CSV of news articles via CLI
- Identifies geopolitical escalation events across five defined categories
- Produces structured risk scores and confidence ratings
- Prioritises precision over recall throughout

---

## Implementation Phases

---

### Phase 1: Config and I/O Foundation

**Goal:** Establish the deterministic rules and standard I/O loops to fulfil the baseline specification.

#### Tasks:

1. Set up environment, `.env` file, and API connection test. `config.py` raises `EnvironmentError` immediately if `OPENAI_API_KEY` is missing.

2. Define all constants in `config.py` as named variables:
   - `MODEL_NAME`, `EMBEDDING_MODEL`, `MAX_CONTENT_TOKENS`
   - `NEGATIVE_SIM_THRESHOLD`, `TRIAGE_POSITIVE_THRESHOLD`
   - `EVENT_TAXONOMY` (as provided in SPEC)
   No other file hardcodes model names, thresholds, or weights.

3. Implement `io_csv.py` with column validation on read. If the input CSV is missing any of `pubDate`, `link`, `content`, `source_id`, a `ValueError` is raised before triage begins.

4. Implement rule-based regex triage using `re.search` with `\b` word-boundary anchors that prevents partial matches like `"mine"` matching `"undermine"`.

5. Implement the exact `risk_score` and `confidence` formulas from SPEC in `scoring.py`:
   ```
   risk_score = 0.45 * physical + 0.35 * escalation + 0.20 * evidence
   confidence_score = 0.5 * evidence + 0.3 * signal + 0.2 * model
   ```

---

### Phase 2: Optimisation

### Stage 1 — Semantic Triage

**Goal:** Reduce false positives and API costs before the expensive LLM step.

#### Tasks:

1. Integrate `text-embedding-3-small` into `triage.py`. Embed keyword-passed articles and compare cosine similarity against positive taxonomy centroids.

2. Implement the Negative Taxonomy anti-filter. Pre-compute embeddings for three noise categories:
   - Historical documentaries and retrospectives
   - Domestic elections and local politics
   - General stock market and financial reporting

   If an article's embedding aligns closer to any noise centroid than to all positive centroids, and the noise similarity exceeds `NEGATIVE_SIM_THRESHOLD`, the article is blocked.

3. Cache all taxonomy embeddings to `data/.taxonomy_cache.pkl` on first run. Every subsequent startup loads from disk and eliminates 8 redundant API calls per run.

---

### Stage 2 — LLM Precision

**Goal:** Produce calibrated, consistent scores and eliminate schema failures.

#### Tasks:

1. Upgrade the prompt to Chain-of-Thought (CoT) architecture. The model must write `step_by_step_analysis` before generating any score which forces reasoning before commitment, not rationalisation after.

2. Add explicit `0.0` and `1.0` anchor examples to all four scoring dimensions in the rubric (physical, escalation, evidence, signal). The `signal_score` rubric follows the SPEC definition:
   - `0.0` = contradictions, mixed signals, unclear if event occurred
   - `1.0` = multiple sentences consistently support the same event, no contradictions

3. Add calibration rules to the prompt preventing score inflation on rhetoric:
   - Political statements with no physical action → `physical_score` must be `0.0–0.15`
   - Unconfirmed / alleged events → `evidence_score` must be `0.0–0.40`
   - Single actor, no regional spillover → `escalation_score` must be `0.0–0.30`
   - Ambiguous articles → always score conservatively

4. Move the system persona to the `system` message in `classifier.py`. The `system` message frames the model's identity for the full conversation which is more consistent role adherence than embedding the persona inside the user prompt.

5. Implement Pydantic Structured Outputs with `ge=0.0, le=1.0` constraints on all four score fields. Values outside `[0, 1]` are rejected at the schema level before reaching `scoring.py`.

---

### Phase 3: Scaling and Cost Reduction

**Goal:** Speed up processing and reduce token costs without sacrificing accuracy.

#### Tasks:

1. **Token-based truncation using `tiktoken`:** Replace `content[:3000]` character slicing with exact token-based truncation:
   ```python
   _encoder = tiktoken.encoding_for_model("gpt-4o-mini")
   tokens = _encoder.encode(content)[:MAX_CONTENT_TOKENS]  # 700 tokens
   truncated_content = _encoder.decode(tokens)
   ```
   This guarantees exactly `MAX_CONTENT_TOKENS` (700) tokens regardless of character density, accent marks, or special characters. Character slicing produces unpredictable token counts (500–1,500 tokens for the same 3,000 characters). The encoder is initialised once at module level, not per article.

2. **`max_tokens=350`** applied to all completion calls that caps output billing and enforces concise rationales.

3. **Asynchronous architecture** via `ThreadPoolExecutor(max_workers=10)` processes up to 10 articles concurrently. Prompt batching was explicitly rejected to prevent cross-article context bleed and preserve per-article precision.

4. **Index-based result ordering** eliminates the O(n²) sort. Each `Future` is mapped to its original array position at submission time. Results are slotted into a dict by position as they arrive and reconstructed in O(n):
   ```python
   future_to_idx = {executor.submit(process_single_article, idx, row): idx
                    for idx, row in enumerate(articles)}
   indexed_results = {}
   for future in as_completed(future_to_idx):
       indexed_results[future_to_idx[future]] = future.result()
   results = [indexed_results[i] for i in range(len(articles))]
   ```

---

### Phase 4: Robustness and Correctness

**Goal:** Ensure no article produces a silent failure, and every output row is interpretable.

#### Tasks:

1. **Retry logic in `classifier.py`** with exponential backoff:
   - `RateLimitError` → wait `2^attempt` seconds (1s, 2s, 4s), retry up to 3 times
   - `APIConnectionError` → retry once after 1s
   - All other exceptions → return `None` immediately, activate fallback path
   Rate limits are temporary; the current code treats them the same as permanent errors. Backoff resolves them without pipeline interruption.

2. **Wire in `calculate_fallback_scores()`** from `scoring.py`. When `classify_article()` returns `None`, instead of assigning silent zero scores:
   ```python
   if llm_data is None:
       llm_data = calculate_fallback_scores(detected_keywords)
       row['processing_status'] = 'fallback'
   else:
       row['processing_status'] = 'success'
   ```
   Fallback produces heuristic scores based on keyword severity which is far more informative than uniform zeros.

3. **`processing_status` column** added to every output row with three possible values:
   - `success` — LLM scored, fully reliable
   - `fallback` — API failed, keyword heuristic used
   - `triage_rejected` — filtered before LLM, `risk_score=0.0` is intentional

   Without this column, a `risk_score` of `0.0` is ambiguous across all three cases.

---

## Technical Decisions

| Decision | Rationale |
|---|---|
| `gpt-4o-mini` as default model | Balances cost and quality; easily swapped by changing `MODEL_NAME` in `config.py` |
| All constants in `config.py` | Single place to tune model, thresholds, and weights — no magic numbers in logic files |
| Token-based truncation via `tiktoken` | Guarantees exact `MAX_CONTENT_TOKENS` (700) tokens regardless of text character density; character slicing is unpredictable |
| CoT with `step_by_step_analysis` first | Forces the model to reason before scoring — prevents score rationalisation, produces more calibrated outputs |
| Calibration rules in prompt | Directly encodes SPEC's "pure rhetoric stays below 0.40" requirement; the model does not apply this restraint without explicit instruction |
| `signal_score` anchored to SPEC | Uses SPEC's "High when / Low when" language translated to `0.0/1.0` anchors — consistent with how the other three dimensions are defined |
| Pydantic `ge/le` constraints | Score values outside `[0, 1]` rejected at schema level, not silently passed to `scoring.py` |
| Retry with exponential backoff | Rate limits are temporary; treating them as permanent errors causes unnecessary fallback use |
| Fallback scorer wired in | API failures produce informative heuristic scores instead of silent uniform zeros |
| `processing_status` column | Makes every `0.0` score interpretable — triage rejection vs. genuine low risk vs. API failure |
| Index-based result ordering | O(n) reconstruction vs. O(n²) `list.index()` scan — matters at scale |
| Async isolated calls (no batching) | Prevents context bleed between articles; precision over throughput |
| Negative taxonomy with disk cache | Blocks noise that passes keyword checks; cached to eliminate repeated startup API calls |

---

## Known Trade-offs and Limitations

| Trade-off | Impact |
|---|---|
| Rejection of prompt batching | Slight increase in redundant system-prompt token costs, traded for guaranteed per-article precision and no context bleed |
| 700-token truncation loses article tail | Risk of missing confirmatory detail in later paragraphs; mitigated by journalistic inverted pyramid structure |
| Fallback scores are heuristics only | `processing_status='fallback'` rows should be treated with caution — keyword severity is a rough proxy for actual risk |
| LLM non-determinism at temperature 0.0 | Minimised but not eliminated; identical articles may produce marginally different scores across runs |
| Cost scales with triage pass-rate | High-noise datasets with many broad keyword matches increase API cost; embedding cache mitigates re-run cost |
| Geographic boundary ambiguity | LLM occasionally struggles with adjacent categories (e.g., Oman infrastructure vs. UAE infrastructure) |