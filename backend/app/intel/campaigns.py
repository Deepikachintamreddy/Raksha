# -*- coding: utf-8 -*-
# Raksha — Campaign Intelligence Analysis Module
# Extracts entities and clusters cases into campaigns.

from __future__ import annotations
import re
import json
import logging
from typing import Optional, List, Dict
from datetime import datetime, timezone

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from pydantic import BaseModel, Field
from google.genai import types
from ..llm.wrapper import get_llm

from ..store import get_store, CaseRecord, CaseEntity

logger = logging.getLogger("raksha.intel.campaigns")

# Union-Find structure for clustering
class UnionFind:
    def __init__(self, elements):
        self.parent = {el: el for el in elements}
        self.rank = {el: 0 for el in elements}

    def find(self, i):
        if self.parent[i] == i:
            return i
        self.parent[i] = self.find(self.parent[i])
        return self.parent[i]

    def union(self, i, j):
        root_i = self.find(i)
        root_j = self.find(j)
        if root_i != root_j:
            if self.rank[root_i] < self.rank[root_j]:
                self.parent[root_i] = root_j
            elif self.rank[root_i] > self.rank[root_j]:
                self.parent[root_j] = root_i
            else:
                self.parent[root_j] = root_i
                self.rank[root_i] += 1
            return True
        return False


def extract_entities_regex(text: str) -> list[dict]:
    """Extract suspect identifiers (phone, upi, account, url, agency) using regex."""
    entities = []

    # 1. Indian Phone Numbers (+91 or 10-digit starting with 6-9)
    phones = re.findall(r"\b(?:\+91[\-\s]?)?[6789]\d{9}\b", text)
    for p in set(phones):
        entities.append({"type": "phone", "value": p.strip()})

    # 2. UPI IDs (e.g. name@bank, scammer@ybl)
    upi_pattern = r"\b[a-zA-Z0-9\.\-_]+@[a-zA-Z]{3,15}\b"
    upis = re.findall(upi_pattern, text)
    for u in set(upis):
        entities.append({"type": "upi", "value": u.lower().strip()})

    # 3. Bank Account Numbers (9 to 18 digits)
    # Exclude matches that are actually phone numbers or UPI domain parts by checking boundaries
    accounts = re.findall(r"\b\d{9,18}\b", text)
    # Filter out matches that overlap with phone numbers
    phone_set = set(phones)
    for a in set(accounts):
        if not any(a in p for p in phone_set):
            entities.append({"type": "account", "value": a.strip()})

    # 4. URLs
    urls = re.findall(r"\b(?:https?://)?[a-zA-Z0-9\.\-]+\.[a-zA-Z]{2,6}(?:/[a-zA-Z0-9\.\-\?&\+=\#]*)?\b", text)
    for url in set(urls):
        url_lower = url.lower()
        # Filter out common false positives like "fedex.com" or "dhl.com" if they are safe, but keep suspicious/lookalike ones
        if not any(safe in url_lower for safe in ["github.com", "google.com", "localhost", "127.0.0.1"]):
            entities.append({"type": "url", "value": url.strip()})

    # 5. Claimed Agency Names (CBI, ED, TRAI, Police, Customs, etc.)
    agency_pattern = r"\b(cbi|central bureau of investigation|ed|enforcement directorate|customs|trai|dot|department of telecommunications|police|cyber cell|cyber crime|supreme court|high court|rbi|reserve bank of india|sbi|state bank of india|pnb|hdfc|icici)\b"
    agencies = re.findall(agency_pattern, text, re.IGNORECASE)
    for agency in set(agencies):
        entities.append({"type": "agency", "value": agency.upper().strip()})

    return entities


class ExtractedEntities(BaseModel):
    phones: list[str] = Field(default_factory=list, description="Extract suspect phone numbers")
    upis: list[str] = Field(default_factory=list, description="Extract suspect UPI IDs")
    accounts: list[str] = Field(default_factory=list, description="Extract suspect bank account numbers")
    urls: list[str] = Field(default_factory=list, description="Extract suspect website links or URLs")
    agencies: list[str] = Field(default_factory=list, description="Extract claimed law enforcement or government agencies")


def extract_entities_llm_sync(text: str) -> list[dict]:
    """Fallback LLM-based entity extraction when regex finds no key infrastructure."""
    import os
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key or api_key == "your-gemini-api-key-here":
        logger.warning("Skipping LLM entity extraction: GEMINI_API_KEY not configured.")
        return []

    try:
        llm = get_llm()
        client = llm._get_client()

        config = types.GenerateContentConfig(
            system_instruction=(
                "You are an expert fraud investigator. Extract all suspect infrastructure identifiers "
                "from the given message/transcript. Be conservative and only extract clear suspect entities."
            ),
            temperature=0.1,
            response_mime_type="application/json",
            response_schema=ExtractedEntities,
        )

        response = client.models.generate_content(
            model=llm.model_name,
            contents=text,
            config=config,
        )
        data = json.loads(response.text)
        entities = []
        for p in data.get("phones", []):
            entities.append({"type": "phone", "value": p})
        for u in data.get("upis", []):
            entities.append({"type": "upi", "value": u})
        for a in data.get("accounts", []):
            entities.append({"type": "account", "value": a})
        for url in data.get("urls", []):
            entities.append({"type": "url", "value": url})
        for ag in data.get("agencies", []):
            entities.append({"type": "agency", "value": ag})
        return entities
    except Exception as e:
        logger.warning(f"Gemini LLM entity extraction failed: {e}")
        return []


def extract_entities(text: str) -> list[dict]:
    """Extract entities using regex first, with LLM fallback if no infrastructure found."""
    entities = extract_entities_regex(text)

    # Fallback if no phone, upi, account, or url is found
    has_infra = any(e["type"] in ["phone", "upi", "account", "url"] for e in entities)
    if not has_infra:
        logger.info("No infrastructure entities found via regex. Triggering LLM fallback extraction.")
        llm_entities = extract_entities_llm_sync(text)
        existing = {e["value"] for e in entities}
        for le in llm_entities:
            if le["value"] not in existing:
                entities.append(le)

    return entities


async def run_entity_extraction():
    """Extract and save entities for all cases that don't have them yet."""
    store = get_store()
    cases = store.list_cases(limit=1000)
    for case in cases:
        existing = store.get_entities_for_case(case.case_id)
        if not existing:
            entities = extract_entities(case.input_text)
            store.log_entities(case.case_id, entities)


def compute_campaign_clusters() -> list[dict]:
    """
    Cluster cases into campaigns based on:
    1. Shared entities (phone, upi, account, url)
    2. Cosine similarity >= 0.85 (Gemini embeddings first, TF-IDF fallback)
    """
    store = get_store()
    cases = store.get_all_cases_asc()
    if not cases:
        return []

    # Make sure entities are populated
    for case in cases:
        existing = store.get_entities_for_case(case.case_id)
        if not existing:
            entities = extract_entities(case.input_text)
            store.log_entities(case.case_id, entities)

    case_ids = [c.case_id for c in cases]
    uf = UnionFind(case_ids)

    # 1. Group by shared entities
    entity_to_cases = {}
    for case in cases:
        entities = store.get_entities_for_case(case.case_id)
        for ent in entities:
            # We don't link solely by agency name because it's too common
            if ent.entity_type == "agency":
                continue
            key = (ent.entity_type, ent.entity_value)
            if key not in entity_to_cases:
                entity_to_cases[key] = []
            entity_to_cases[key].append(case.case_id)

    for key, cids in entity_to_cases.items():
        if len(cids) > 1:
            first = cids[0]
            for other in cids[1:]:
                uf.union(first, other)

    # 2. Group by text similarity
    if len(cases) > 1:
        use_tfidf_fallback = True
        import os
        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        if api_key and api_key != "your-gemini-api-key-here":
            try:
                # Attempt to use Gemini embeddings
                embeddings = []
                llm = get_llm()
                for c in cases:
                    emb = llm.get_embedding_sync(c.input_text)
                    embeddings.append(emb)

                import numpy as np
                sim_matrix = cosine_similarity(np.array(embeddings))
                use_tfidf_fallback = False

                for i in range(len(cases)):
                    for j in range(i + 1, len(cases)):
                        if sim_matrix[i, j] >= 0.85:
                            uf.union(cases[i].case_id, cases[j].case_id)
                logger.info("Clustered campaigns successfully using Gemini embeddings.")
            except Exception as e:
                logger.warning(f"Failed to use Gemini embeddings, falling back to TF-IDF: {e}")

        if use_tfidf_fallback:
            # TF-IDF cosine fallback
            vectorizer = TfidfVectorizer(stop_words="english")
            tfidf = vectorizer.fit_transform([c.input_text for c in cases])
            sim_matrix = cosine_similarity(tfidf)

            for i in range(len(cases)):
                for j in range(i + 1, len(cases)):
                    if sim_matrix[i, j] >= 0.85:
                        uf.union(cases[i].case_id, cases[j].case_id)
            logger.info("Clustered campaigns successfully using TF-IDF fallback.")

    # 3. Collect clusters
    campaigns_dict = {}
    for cid in case_ids:
        root = uf.find(cid)
        if root not in campaigns_dict:
            campaigns_dict[root] = []
        campaigns_dict[root].append(cid)

    # Convert to campaign objects
    campaigns = []
    case_lookup = {c.case_id: c for c in cases}

    for root_id, cids in campaigns_dict.items():
        # A campaign needs to have at least 2 linked cases to show up as a "network"
        if len(cids) < 2:
            continue

        # Compile campaign metadata
        campaign_cases = [case_lookup[cid] for cid in cids]
        campaign_cases.sort(key=lambda x: x.timestamp)

        first_seen = campaign_cases[0].timestamp.isoformat() + "Z" if campaign_cases[0].timestamp else ""
        victim_count = len(cids)

        # Collect entities
        all_entities = []
        entity_values = set()
        for cid in cids:
            ents = store.get_entities_for_case(cid)
            for ent in ents:
                if ent.entity_value not in entity_values:
                    entity_values.add(ent.entity_value)
                    all_entities.append({
                        "type": ent.entity_type,
                        "value": ent.entity_value
                    })

        # Script excerpt (common template or first case text)
        excerpt = campaign_cases[0].input_text
        if len(excerpt) > 120:
            excerpt = excerpt[:120] + "..."

        campaigns.append({
            "campaign_id": f"CAMP-{root_id[:8].upper()}",
            "case_ids": cids,
            "entities": all_entities,
            "victim_count": victim_count,
            "first_seen": first_seen,
            "common_script_excerpt": excerpt,
        })

    # Sort campaigns by victim count descending
    campaigns.sort(key=lambda x: x["victim_count"], reverse=True)
    return campaigns
