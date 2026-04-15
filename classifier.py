import json
from pydantic import BaseModel, Field
from typing import List
from openai import OpenAI
from config import OPENAI_API_KEY, MODEL_NAME
from prompt_builder import build_classification_prompt

client = OpenAI(api_key=OPENAI_API_KEY)

# --- STRATEGY : Pydantic Structured Outputs Schema ---
# This mathematically guarantees the LLM will return these exact keys and data types.
class GeopoliticalRiskAssessment(BaseModel):
    step_by_step_analysis: str = Field(description="Briefly debate the facts of the article against the rubric.")
    physical_score: float = Field(description="Score between 0.0 and 1.0.")
    escalation_score: float = Field(description="Score between 0.0 and 1.0.")
    evidence_score: float = Field(description="Score between 0.0 and 1.0.")
    signal_score: float = Field(description="Score between 0.0 and 1.0.")
    event_labels: List[str] = Field(description="List of detected event categories from the taxonomy.")
    rationale: str = Field(description="A highly professional, 1-sentence final justification for these scores.")

def classify_article(content):
    prompt = build_classification_prompt(content)
    
    try:
        # Notice we use client.beta.chat.completions.parse for Structured Outputs
        response = client.beta.chat.completions.parse(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "You are a precise geopolitical risk analyst."},
                {"role": "user", "content": prompt}
            ],
            response_format=GeopoliticalRiskAssessment, # Enforces the strict schema
            temperature=0.0,
            max_tokens=350 # --- STRATEGY 4: Capping tokens to reduce costs ---
        )
        
        # OpenAI automatically parses the Pydantic model for us
        parsed_data = response.choices[0].message.parsed
        
        # Convert it back to a standard Python dictionary for the rest of your app
        return parsed_data.model_dump()
        
    except Exception as e:
        print(f"\n--- OPENAI ERROR ---\n{e}\n--------------------\n")
        return None