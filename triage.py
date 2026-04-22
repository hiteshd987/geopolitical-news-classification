import re
import os
import math
import pickle
from openai import OpenAI
from config import (
    EVENT_TAXONOMY,
    OPENAI_API_KEY,
    EMBEDDING_MODEL,           # was hardcoded as "text-embedding-3-small"
    NEGATIVE_SIM_THRESHOLD,    # was hardcoded as 0.30
    TRIAGE_POSITIVE_THRESHOLD  # was hardcoded as 0.25
)

# Initialize the OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

print("Initializing OpenAI Embedding API (With Negative Filtering)...")

# --- POSITIVE TAXONOMY ---
TAXONOMY_DESCRIPTIONS = [
    "Closure or blockade of the Strait of Hormuz, naval mines, or tanker attacks by IRGC.",
    "Attacks, seizures, or amphibious landings at Kharg Island oil export terminal.",
    "Drone or missile attacks on critical Gulf energy infrastructure, refineries, or pipelines in Saudi Arabia or UAE.",
    "Direct ground troop deployment or coalition multinational force intervention by Saudi Arabia or UAE.",
    "Houthi missile attacks on merchant shipping or diversions in the Red Sea and Bab el-Mandeb."
]

# --- NEGATIVE TAXONOMY (The Anti-Filter) ---
NEGATIVE_TAXONOMY_DESCRIPTIONS = [
    "A historical documentary, retrospective review, or historical analysis of past conflicts in the Middle East.",
    "Global stock market analysis, general crude oil price fluctuations, or macroeconomic financial reporting.",
    "A purely local domestic crime, political election, or local cultural exhibition.",
    # "Academic research paper or policy think-tank analysis with no operational urgency.",
    # "Satirical news article or opinion commentary with no factual reporting.",
    # "Sports or entertainment news that incidentally mentions geographic locations."
]



def get_embedding(text):
    text = text[:8000] 
    response = client.embeddings.create(input=text, model=EMBEDDING_MODEL)
    return response.data[0].embedding

TAXONOMY_CACHE_PATH = "data/.taxonomy_cache.pkl"

def _load_or_compute_taxonomy_embeddings():
    if os.path.exists(TAXONOMY_CACHE_PATH):
        print("Loading taxonomy embeddings from cache...")
        with open(TAXONOMY_CACHE_PATH, 'rb') as f:
            return pickle.load(f)

    print("Computing taxonomy embeddings (first run only)...")
    pos = [get_embedding(desc) for desc in TAXONOMY_DESCRIPTIONS]
    neg = [get_embedding(desc) for desc in NEGATIVE_TAXONOMY_DESCRIPTIONS]

    os.makedirs("data", exist_ok=True)
    with open(TAXONOMY_CACHE_PATH, 'wb') as f:
        pickle.dump((pos, neg), f)

    print("Taxonomy embeddings cached.")
    return pos, neg

taxonomy_embeddings, negative_embeddings = _load_or_compute_taxonomy_embeddings()

def cosine_similarity_pure(vec1, vec2):
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    magnitude1 = math.sqrt(sum(a * a for a in vec1))
    magnitude2 = math.sqrt(sum(b * b for b in vec2))
    if magnitude1 == 0 or magnitude2 == 0: return 0.0
    return dot_product / (magnitude1 * magnitude2)

def advanced_triage(content, threshold=TRIAGE_POSITIVE_THRESHOLD):
    content_lower = content.lower()
    matched_keywords = set()
    
    for category, keywords in EVENT_TAXONOMY.items():
        for keyword in keywords:
            if re.search(r'\b' + re.escape(keyword) + r'\b', content_lower):
                matched_keywords.add(keyword)
                
    if not matched_keywords:
        return [] 
        
    try:
        article_embedding = get_embedding(content)
        
        # Calculate similarities for BOTH positive and negative
        pos_similarities = [cosine_similarity_pure(article_embedding, tax_emb) for tax_emb in taxonomy_embeddings]
        neg_similarities = [cosine_similarity_pure(article_embedding, neg_emb) for neg_emb in negative_embeddings]
        
        max_pos = max(pos_similarities)
        max_neg = max(neg_similarities)
        
        # If it sounds more like a history lesson/stock update than an attack, block it.
        if max_neg > max_pos and max_neg > NEGATIVE_SIM_THRESHOLD:
            return [] # Blocked by negative filter
            
        if max_pos >= threshold:
            return list(matched_keywords)
        else:
            return []
            
    except Exception as e:
        print(f"  [Warning] Embedding API Failed ({e}). Falling back to strict keyword match.")
        return list(matched_keywords)

# basic triage regex
# import re
# from config import EVENT_TAXONOMY

# def triage_article(content):
#     """
#     Stage 1: Rule-based keyword filtering.
#     Returns a list of unique matched keywords found in the text.
#     """
#     content_lower = content.lower()
#     matched_keywords = set()
    
#     for category, keywords in EVENT_TAXONOMY.items():
#         for keyword in keywords:
#             # \b ensures we match whole words/phrases, not substrings
#             if re.search(r'\b' + re.escape(keyword) + r'\b', content_lower):
#                 matched_keywords.add(keyword)
                
#     return list(matched_keywords)