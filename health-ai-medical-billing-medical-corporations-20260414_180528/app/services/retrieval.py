import hashlib
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any


_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_-]*", re.IGNORECASE)
DEFAULT_EMBEDDING_DIMENSIONS = 128
HASH_EMBEDDING_MODEL = "claimguard-hash-embedding-v1"


@dataclass
class SourceChunk:
    chunk_id: str
    source_id: str
    title: str
    source_type: str
    text: str
    jurisdiction: str | None = None
    payer_type: str | None = None
    date: str | None = None
    source_url: str | None = None
    page_number: str | None = None
    phi_status: str = "no_phi"
    license_status: str = "review_required"
    extra_metadata: dict[str, Any] = field(default_factory=dict)

    def citation(self) -> str:
        page = f"#page={self.page_number}" if self.page_number else f"#{self.chunk_id}"
        if self.source_url:
            return f"{self.source_url}{page}"
        return f"{self.source_id}{page}"

    def to_result(self, score: float) -> dict:
        return {
            "source_id": self.source_id,
            "title": self.title,
            "source_type": self.source_type,
            "citation": self.citation(),
            "text": self.text,
            "jurisdiction": self.jurisdiction,
            "payer_type": self.payer_type,
            "date": self.date,
            "phi_status": self.phi_status,
            "license_status": self.license_status,
            "score": score,
        }


def _tokens(text: str) -> list[str]:
    return [token.lower() for token in _TOKEN_RE.findall(text)]


def hash_embedding(
    text: str,
    *,
    dimensions: int = DEFAULT_EMBEDDING_DIMENSIONS,
) -> list[float]:
    if dimensions <= 0:
        raise ValueError("Embedding dimensions must be positive")

    vector = [0.0] * dimensions
    token_counts = Counter(_tokens(text))
    if not token_counts:
        return vector

    for token, count in token_counts.items():
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign * (1.0 + math.log(count))

    magnitude = math.sqrt(sum(value * value for value in vector))
    if magnitude == 0:
        return vector
    return [round(value / magnitude, 8) for value in vector]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    return sum(left_value * right_value for left_value, right_value in zip(left, right))


def chunk_document(
    text: str,
    *,
    source_id: str,
    title: str,
    source_type: str,
    jurisdiction: str | None = None,
    payer_type: str | None = None,
    date: str | None = None,
    source_url: str | None = None,
    phi_status: str = "contains_phi",
    license_status: str = "user_provided_private",
    chunk_size: int = 900,
    overlap: int = 120,
) -> list[SourceChunk]:
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return []

    chunks: list[SourceChunk] = []
    start = 0
    chunk_number = 1
    while start < len(normalized):
        end = min(len(normalized), start + chunk_size)
        chunk_text = normalized[start:end].strip()
        if chunk_text:
            chunks.append(
                SourceChunk(
                    chunk_id=f"{source_id}-chunk-{chunk_number:03d}",
                    source_id=source_id,
                    title=title,
                    source_type=source_type,
                    text=chunk_text,
                    jurisdiction=jurisdiction,
                    payer_type=payer_type,
                    date=date,
                    source_url=source_url,
                    phi_status=phi_status,
                    license_status=license_status,
                )
            )
            chunk_number += 1
        if end == len(normalized):
            break
        start = max(0, end - overlap)
    return chunks


class KeywordRetrievalIndex:
    def __init__(self, chunks: list[SourceChunk] | None = None):
        self.chunks = chunks or []
        self._chunk_tokens = [Counter(_tokens(chunk.text)) for chunk in self.chunks]

    def add_chunks(self, chunks: list[SourceChunk]) -> None:
        for chunk in chunks:
            self.chunks.append(chunk)
            self._chunk_tokens.append(Counter(_tokens(chunk.text)))

    def search(self, query: str, *, top_k: int = 5) -> list[dict]:
        query_tokens = Counter(_tokens(query))
        if not query_tokens:
            return []

        scored: list[tuple[float, SourceChunk]] = []
        for chunk, token_counts in zip(self.chunks, self._chunk_tokens):
            overlap = sum(min(token_counts[token], count) for token, count in query_tokens.items())
            if overlap <= 0:
                continue
            score = overlap / max(1, len(query_tokens))
            scored.append((score, chunk))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [chunk.to_result(score) for score, chunk in scored[:top_k]]


class HashEmbeddingRetrievalIndex:
    def __init__(
        self,
        chunks: list[SourceChunk] | None = None,
        *,
        dimensions: int = DEFAULT_EMBEDDING_DIMENSIONS,
    ):
        self.chunks = chunks or []
        self.dimensions = dimensions
        self._embeddings = [self._chunk_embedding(chunk) for chunk in self.chunks]

    def _chunk_embedding(self, chunk: SourceChunk) -> list[float]:
        stored = chunk.extra_metadata.get("embedding")
        if isinstance(stored, list) and len(stored) == self.dimensions:
            return [float(value) for value in stored]
        return hash_embedding(chunk.text, dimensions=self.dimensions)

    def search(self, query: str, *, top_k: int = 5) -> list[dict]:
        query_embedding = hash_embedding(query, dimensions=self.dimensions)
        if not any(query_embedding):
            return []

        scored = [
            (cosine_similarity(query_embedding, embedding), chunk)
            for chunk, embedding in zip(self.chunks, self._embeddings)
        ]
        scored = [(score, chunk) for score, chunk in scored if score > 0]
        scored.sort(key=lambda item: item[0], reverse=True)
        return [chunk.to_result(score) for score, chunk in scored[:top_k]]


class HybridRetrievalIndex:
    def __init__(
        self,
        chunks: list[SourceChunk] | None = None,
        *,
        dimensions: int = DEFAULT_EMBEDDING_DIMENSIONS,
        keyword_weight: float = 0.55,
        embedding_weight: float = 0.45,
    ):
        self.chunks = chunks or []
        self.keyword_index = KeywordRetrievalIndex(self.chunks)
        self.embedding_index = HashEmbeddingRetrievalIndex(
            self.chunks,
            dimensions=dimensions,
        )
        self.keyword_weight = keyword_weight
        self.embedding_weight = embedding_weight

    def search(self, query: str, *, top_k: int = 5) -> list[dict]:
        keyword_results = self.keyword_index.search(query, top_k=max(top_k, len(self.chunks)))
        embedding_results = self.embedding_index.search(query, top_k=max(top_k, len(self.chunks)))
        scores: dict[str, tuple[dict, float]] = {}

        for result in keyword_results:
            chunk_id = result["citation"]
            existing = scores.get(chunk_id, (result, 0.0))[1]
            scores[chunk_id] = (result, existing + (self.keyword_weight * result["score"]))
        for result in embedding_results:
            chunk_id = result["citation"]
            existing = scores.get(chunk_id, (result, 0.0))[1]
            scores[chunk_id] = (result, existing + (self.embedding_weight * result["score"]))

        ranked = []
        for result, score in scores.values():
            ranked_result = dict(result)
            ranked_result["score"] = round(score, 6)
            ranked.append(ranked_result)
        ranked.sort(key=lambda item: item["score"], reverse=True)
        return ranked[:top_k]


def build_default_rule_chunks() -> list[SourceChunk]:
    return [
        SourceChunk(
            chunk_id="SRC-DOL-CLAIMS-commercial-internal-appeal",
            source_id="SRC-DOL-CLAIMS",
            title="DOL/EBSA Filing a Claim for Your Health Benefits",
            source_type="public_rule",
            payer_type="commercial_erisa",
            source_url="https://www.dol.gov/agencies/ebsa/about-ebsa/our-activities/resource-center/publications/filing-a-claim-for-your-health-benefits",
            text=(
                "Internal appeals for group health plan adverse benefit determinations "
                "generally must be filed within 180 days after receiving notice of "
                "denial. Plan terms, denial-letter instructions, and local rules must "
                "still be verified."
            ),
            phi_status="no_phi",
            license_status="public_rule",
        ),
        SourceChunk(
            chunk_id="SRC-HCG-EXTERNAL-timing",
            source_id="SRC-HCG-EXTERNAL",
            title="HealthCare.gov External Review",
            source_type="public_rule",
            payer_type="commercial_aca",
            source_url="https://www.healthcare.gov/appeal-insurance-company-decision/external-review/",
            text=(
                "External review requests are commonly due within four months after "
                "receiving a final adverse determination, and standard external reviews "
                "are decided no later than 45 days after request receipt. State or "
                "federal process details must be verified."
            ),
            phi_status="no_phi",
            license_status="public_rule",
        ),
        SourceChunk(
            chunk_id="SRC-MEDICARE-FFS-1-redetermination",
            source_id="SRC-MEDICARE-FFS-1",
            title="CMS FFS Redetermination",
            source_type="public_rule",
            payer_type="medicare_ffs",
            source_url="https://www.cms.gov/medicare/appeals-grievances/fee-for-service/first-level-appeal-redetermination-medicare-contractor",
            text=(
                "Medicare Fee-for-Service redetermination requests are due 120 days "
                "from receipt of the initial claim determination. Receipt is presumed "
                "five calendar days after notice date unless evidence shows otherwise. "
                "Minor errors and omissions should be evaluated for correction or reopening."
            ),
            phi_status="no_phi",
            license_status="public_rule",
        ),
        SourceChunk(
            chunk_id="SRC-MEDICARE-MA-RECON-timing",
            source_id="SRC-MEDICARE-MA-RECON",
            title="CMS Medicare Advantage Reconsideration",
            source_type="public_rule",
            payer_type="medicare_advantage",
            source_url="https://www.cms.gov/medicare/appeals-grievances/managed-care/reconsideration-advantage-health-plan-part-c",
            text=(
                "Medicare Advantage reconsideration requests must be filed with the "
                "MA plan within 65 calendar days from the organization determination "
                "notice. Expedited and standard decision clocks depend on request type."
            ),
            phi_status="no_phi",
            license_status="public_rule",
        ),
        SourceChunk(
            chunk_id="SRC-MEDICAID-CFR-continuation",
            source_id="SRC-MEDICAID-CFR",
            title="42 CFR Part 438 Subpart F",
            source_type="public_rule",
            payer_type="medicaid_managed_care",
            source_url="https://www.ecfr.gov/current/title-42/chapter-IV/subchapter-C/part-438/subpart-F",
            text=(
                "Medicaid managed-care appeals, expedited appeals, state fair hearings, "
                "and continuation-of-benefits rules are controlled by 42 CFR Part 438 "
                "Subpart F and state-specific processes. Continuation of benefits may "
                "require action by the later of 10 calendar days after notice is sent "
                "or the intended effective date."
            ),
            phi_status="no_phi",
            license_status="public_rule",
        ),
        SourceChunk(
            chunk_id="SRC-HIPAA-MIN-appeal-packet",
            source_id="SRC-HIPAA-MIN",
            title="HHS HIPAA Minimum Necessary Requirement",
            source_type="privacy_rule",
            source_url="https://www.hhs.gov/hipaa/for-professionals/privacy/guidance/minimum-necessary-requirement/index.html",
            text=(
                "Appeal packets and training examples should use the minimum necessary "
                "PHI for the appeal purpose and exclude unrelated records or identifiers "
                "unless a controlling source requires them."
            ),
            phi_status="no_phi",
            license_status="public_rule",
        ),
    ]
