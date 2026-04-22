import random
from io_csv import read_csv
from triage import advanced_triage
from classifier import classify_article
import tiktoken

def calculate_costs(articles):
    """Calculates the estimated cost per 100 articles by dynamically counting dataset tokens."""
    print("\n" + "="*50)
    print(" DATA-DRIVEN COST AWARENESS REPORT")
    print("="*50)
    
    # Initialize the exact tokenizer used by gpt-4o-mini
    encoder = tiktoken.encoding_for_model("gpt-4o-mini")
    
    total_old_input_tokens = 0
    total_new_input_tokens = 0
    
    # Analyze the actual dataset to get exact token counts
    for row in articles:
        content = row.get('content', '')
        
        # Count tokens for the full article (Before Optimization)
        total_old_input_tokens += len(encoder.encode(content))
        
        # Count tokens for the truncated article (After Optimization)
        total_new_input_tokens += len(encoder.encode(content[:3000]))
        
    # Calculate the averages
    num_articles = len(articles)
    avg_old_input = total_old_input_tokens / num_articles
    avg_new_input = total_new_input_tokens / num_articles
    
    # Add ~150 tokens to account for our System Prompt & Rubric
    avg_old_input += 150
    avg_new_input += 150
    
    # Output token estimation (remains an estimate since we can't know exactly 
    # what the LLM will generate until it runs, but we cap it)
    avg_old_output = 250 
    avg_new_output = 150 
    
    # gpt-4o-mini pricing (per 1 million tokens)
    INPUT_COST_PER_M = 0.150
    OUTPUT_COST_PER_M = 0.600
    
    # Calculate New Costs per 100 articles
    cost_100_input = (100 * avg_new_input / 1_000_000) * INPUT_COST_PER_M
    cost_100_output = (100 * avg_new_output / 1_000_000) * OUTPUT_COST_PER_M
    total_100_cost = cost_100_input + cost_100_output
    
    print(f"Model: gpt-4o-mini")
    print(f"Old Analyzed Tokens/Article:  {int(avg_old_input)} In / {avg_old_output} Out")
    print(f"NEW Analyzed Tokens/Article:  {int(avg_new_input)} In / {avg_new_output} Out")
    print(f"---")
    print(f"Cost per 100 Articles:           ${total_100_cost:.4f}")
    print(f"Estimated Cost for Full Dataset: ${(num_articles / 100) * total_100_cost:.4f}")
    
    savings = 100 - ((avg_new_input + avg_new_output) / (avg_old_input + avg_old_output) * 100)
    print(f"Cost Reduction Achieved:         ~{int(savings)}%\n")

def generate_evaluation_sample(articles, sample_size=5):
    """Pulls a random sample of articles and runs them to help you write manual review."""
    print("="*50)
    print(" EVALUATION SAMPLE GENERATOR")
    print("="*50)
    
    # Grab random articles
    sample = random.sample(articles, min(sample_size, len(articles)))
    
    for i, row in enumerate(sample):
        content = row.get('content', '')
        print(f"\n--- Article {i+1} ---")
        print(f"Snippet: {content[:250]}...\n")
        
        # 1. Run Triage (This now includes Negative Embedding filtering automatically!)
        keywords = advanced_triage(content)
        if not keywords:
            print(" Result: Blocked by Semantic Triage (No relevant context, or hit Negative Filter).")
            continue
            
        # 2. Run Classifier
        print(f" Triage Passed: {keywords}. Sending to LLM...")
        
        # We must truncate the content here just like we do in main.py!
        truncated_content = content[:3000]
        
        # This will automatically use your new Pydantic Structured Outputs!
        llm_data = classify_article(truncated_content)
        
        if llm_data:
            print(f" LLM Result:")
            print(f"  Labels: {llm_data.get('event_labels')}")
            print(f"  Scores: Phys: {llm_data.get('physical_score')} | Esc: {llm_data.get('escalation_score')} | Evid: {llm_data.get('evidence_score')}")
            print(f"  Rationale: {llm_data.get('rationale')}")
        else:
            print(" LLM Failed.")

if __name__ == "__main__":
    articles = read_csv("data/newsdata_oil.csv")
    calculate_costs(articles)
    generate_evaluation_sample(articles, sample_size=5)