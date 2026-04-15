import re
import math
from openai import OpenAI
from config import EVENT_TAXONOMY, OPENAI_API_KEY

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
    "A purely local domestic crime, political election, or local cultural exhibition."
]

def get_embedding(text):
    text = text[:8000] 
    response = client.embeddings.create(input=text, model="text-embedding-3-small")
    return response.data[0].embedding

taxonomy_embeddings = [get_embedding(desc) for desc in TAXONOMY_DESCRIPTIONS]
negative_embeddings = [get_embedding(desc) for desc in NEGATIVE_TAXONOMY_DESCRIPTIONS]

def cosine_similarity_pure(vec1, vec2):
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    magnitude1 = math.sqrt(sum(a * a for a in vec1))
    magnitude2 = math.sqrt(sum(b * b for b in vec2))
    if magnitude1 == 0 or magnitude2 == 0: return 0.0
    return dot_product / (magnitude1 * magnitude2)

def advanced_triage(content, threshold=0.25):
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
        if max_neg > max_pos and max_neg > 0.30:
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