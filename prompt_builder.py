def build_classification_prompt(content):
    """
    Constructs an advanced, Chain-of-Thought (CoT) prompt for the LLM.
    """
    prompt = f"""You are an expert geopolitical risk analyst for a major energy firm. 
Your task is to analyze the following news article and grade it based on our Geopolitical Risk Taxonomy.

### STEP 1: EVENT CATEGORIZATION
Select ALL that apply from these exact labels (if none apply, leave empty):
- Hormuz Closure
- Kharg/Khark Attack or Seizure
- Critical Gulf Infrastructure Attacks
- Direct Entry of Saudi/UAE/Coalition Forces
- Red Sea / Bab el-Mandeb Escalation

### STEP 2: SCORING RUBRIC (0.0 to 1.0)
- physical_score: 
  * 0.0 = Pure rhetoric, threats, or diplomatic warnings.
  * 0.5 = Minor physical disruption (e.g., ships rerouting, minor fires).
  * 1.0 = Total destruction or blockade of critical assets.
- escalation_score: 
  * 0.0 = Routine local conflict.
  * 1.0 = Major regional war involving multiple state actors (Saudi, UAE, Iran, US).
- evidence_score: 
  * 0.0 = Rumor, unverified social media, or highly speculative opinion piece.
  * 1.0 = Confirmed multi-source factual reporting.
- signal_score: 
  * How consistently does this match recognized patterns of escalation?

### STEP 3: OUTPUT FORMAT
You MUST return ONLY valid JSON in this exact structure. 
CRITICAL: You must write your `step_by_step_analysis` FIRST before giving the scores.

{{
  "step_by_step_analysis": "Briefly debate the facts of the article against the rubric here.",
  "physical_score": 0.0,
  "escalation_score": 0.0,
  "evidence_score": 0.0,
  "signal_score": 0.0,
  "event_labels": [],
  "rationale": "A highly professional, 1-sentence final justification for these scores."
}}

### ARTICLE CONTENT TO ANALYZE:
{content}
"""
    return prompt