import tiktoken
import argparse
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from io_csv import read_csv, write_csv
from triage import advanced_triage as triage_article
from classifier import classify_article
from scoring import calculate_risk_score, calculate_confidence, calculate_fallback_scores
from config import OPENAI_API_KEY

_encoder = tiktoken.encoding_for_model("gpt-4o-mini")

def process_single_article(idx, row):
    """Worker function to process one article independently."""
    content = row.get('content', '')
    
    # STAGE 1: Advanced Semantic Triage
    detected_keywords = triage_article(content)
    row['keywords_detected'] = ", ".join(detected_keywords)
    
    if not detected_keywords:
        row['event_labels'] = ""
        row['risk_score'] = 0.0
        row['confidence'] = "low"
        row['rationale'] = "Filtered in Semantic Triage."
        row['processing_status'] = 'triage_rejected'    # ← EXIT POINT 1
        print(f"[{idx}] Skipped: No context match.")
        return row
        
    # --- STRATEGY : Inverted Pyramid Truncation ---
    # We only send the top 700 tokens to the LLM. 
    # This halves costs and improves accuracy by removing irrelevant text at the bottom.
    tokens = _encoder.encode(content)[:700]
    truncated_content = _encoder.decode(tokens)

    # STAGE 2: LLM Classification
    print(f"[{idx}] Processing with AI...")
    llm_data = classify_article(truncated_content)
    
    if llm_data is None:
        print(f"[{idx}] ⚠️  API failed. Using keyword fallback.")
        llm_data = calculate_fallback_scores(detected_keywords)
        row['processing_status'] = 'fallback'           # ← EXIT POINT 2
    else:
        row['processing_status'] = 'success'   

    # This block now runs for both LLM success AND fallback
    phys   = llm_data.get('physical_score', 0.0)
    esc    = llm_data.get('escalation_score', 0.0)
    evid   = llm_data.get('evidence_score', 0.0)
    sig    = llm_data.get('signal_score', 0.0)
    labels = llm_data.get('event_labels', [])

    row['event_labels'] = ", ".join(labels)
    row['risk_score']   = calculate_risk_score(phys, esc, evid)
    row['confidence']   = calculate_confidence(evid, sig, labels, llm_data.get('rationale', ''))
    row['rationale']    = llm_data.get('rationale', '')
    print(f"[{idx}] ✅ Risk: {row['risk_score']}")

    return row

def main():
    parser = argparse.ArgumentParser(description="Process Geopolitical News CSV")
    parser.add_argument('--input', required=True, help="Path to input CSV")
    parser.add_argument('--output', required=True, help="Path to output CSV")
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    articles = read_csv(args.input)
    fieldnames = list(articles[0].keys()) + ["event_labels", "risk_score", "confidence", "rationale", "keywords_detected",   "processing_status"]
    
    results = []
    print(f"\n=== Starting ASYNC processing of {len(articles)} articles ===\n")
    
    # The Magic: Run up to 10 articles at the exact same time
    indexed_results = {}

    with ThreadPoolExecutor(max_workers=10) as executor:

        # Map Future → original position index
        future_to_idx = {
            executor.submit(process_single_article, idx, row): idx
            for idx, row in enumerate(articles)
        }

        # Collect results into their correct slots as they finish
        for future in as_completed(future_to_idx):
            original_idx = future_to_idx[future]        # O(1) dict lookup
            indexed_results[original_idx] = future.result()

    # Reconstruct in original order — O(n), no comparisons
    results = [indexed_results[i] for i in range(len(articles))]

    write_csv(results, args.output, fieldnames)
    print(f"\n=== Finished! Results written to {args.output} ===")

if __name__ == "__main__":
    main()