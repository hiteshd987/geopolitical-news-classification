def calculate_risk_score(physical, escalation, evidence):
    """Calculates the final risk score based on the specified formula."""
    score = (0.45 * physical) + (0.35 * escalation) + (0.20 * evidence)
    
    # Clip to [0.00, 1.00] and round to 2 decimal places
    clipped_score = max(0.00, min(1.00, score))
    return round(clipped_score, 2)

def calculate_confidence(evidence, signal, event_labels, rationale):
    """Calculates categorical confidence based on the specified formula."""
    
   # Base: how precise were the event labels?
    if len(event_labels) == 0:
        model_score = 0.2   # No labels = model found nothing definitive
    elif len(event_labels) == 1:
        model_score = 0.9   # Single precise label = high certainty
    elif len(event_labels) == 2:
        model_score = 0.6   # Two labels = moderate certainty
    else:
        model_score = 0.2   # 3+ labels = model is hedging = low certainty

    # Boost if rationale contains specific factual language
    HIGH_QUALITY_TERMS = [
        'confirmed', 'reported', 'deployed', 'launched', 'targeted',
        'destroyed', 'halted', 'seized', 'attacked', 'struck',
        'according to', 'sources say', 'officials stated'
    ]
    term_hits = sum(1 for term in HIGH_QUALITY_TERMS if term in rationale.lower())
    quality_boost = min(term_hits * 0.05, 0.15)  # max +0.15 boost
    model_score = min(model_score + quality_boost, 1.0)
        
    score = (0.5 * evidence) + (0.3 * signal) + (0.2 * model_score)
    
    # Map to categories
    if score >= 0.70:
        return "high"
    elif score >= 0.40: # 0.40 <= score < 0.70
        return "medium"
    else:
        return "low"

def calculate_fallback_scores(detected_keywords):
    """
    If the API fails, estimate the component scores based on the 
    severity of the keywords detected in Stage 1.
    """
    # Baseline scores
    physical = 0.1
    escalation = 0.1
    evidence = 0.3 # We assume medium evidence just because it's published news
    
    # Define high-severity keywords that immediately bump up specific scores
    high_physical_words = ["mine", "tanker attack", "vessel attack", "shipping halt", "sabotage", "drone strike"]
    high_escalation_words = ["coalition", "ground forces", "saudi intervention", "escalation", "regional war"]
    
    # Check our detected keywords against the high-severity lists
    for word in detected_keywords:
        if word in high_physical_words:
            physical = 0.8
        if word in high_escalation_words:
            escalation = 0.8
            
    # Return the estimated sub-scores as a dictionary (mimicking the LLM JSON output)
    return {
        "physical_score": physical,
        "escalation_score": escalation,
        "evidence_score": evidence,
        "signal_score": 0.5, # Default medium signal consistency
        "event_labels": ["Fallback: Keyword Match"],
        "rationale": f"API Failed. Heuristic scores based on severe keywords: {', '.join(detected_keywords)}"
    }