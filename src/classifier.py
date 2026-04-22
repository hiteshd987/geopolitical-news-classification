import json
import time
from pydantic import BaseModel, Field
from typing import List
from openai import OpenAI
from src.config import OPENAI_API_KEY, MODEL_NAME
from src.prompt_builder import build_classification_prompt

client = OpenAI(api_key=OPENAI_API_KEY)

# --- STRATEGY : Pydantic Structured Outputs Schema ---
# This mathematically guarantees the LLM will return these exact keys and data types.
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

def classify_article(content, max_retries=3):
    prompt = build_classification_prompt(content)

    for attempt in range(max_retries):
        try:
            response = client.beta.chat.completions.parse(
                model=MODEL_NAME,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an expert geopolitical risk analyst for a major energy firm. "
                            "You are precise, conservative, and evidence-driven. "
                            "You never inflate scores for political rhetoric without physical action. "
                            "When uncertain, you always score conservatively."
                        )
                    },
                    {"role": "user", "content": prompt}
                ],
                response_format=GeopoliticalRiskAssessment,
                temperature=0.0,
                max_tokens=350
            )
            parsed_data = response.choices[0].message.parsed
            return parsed_data.model_dump()

        except openai.RateLimitError:
            wait = 2 ** attempt  # 1s, then 2s, then 4s
            print(f"  Rate limited. Waiting {wait}s before retry {attempt+1}/{max_retries}...")
            time.sleep(wait)

        except openai.APIConnectionError as e:
            print(f"  Connection error on attempt {attempt+1}: {e}")
            if attempt < max_retries - 1:
                time.sleep(1)

        except Exception as e:
            print(f"\n--- OPENAI ERROR ---\n{e}\n")
            return None  # Non-retryable error, give up immediately

    print("  Max retries reached. Returning None.")
    return None