
from pydantic import BaseModel, Field, model_validator
from typing import Literal
from datetime import datetime
import re


def _parse_confidence(raw) -> float:
    """Robustly convert any LLM confidence value to a 0–100 float.

    Handles:
        90          -> 90.0
        0.9         -> 90.0   (0-1 fraction)
        "90%"       -> 90.0
        "90"        -> 90.0
        "High (90%)"  -> 90.0
        "High"        -> 80.0  (heuristic)
        "Medium"      -> 65.0
        "Low"         -> 40.0
        {"score": 90} -> 90.0
    """
    if raw is None:
        return 75.0

    # Unwrap dict
    if isinstance(raw, dict):
        raw = (raw.get("score") or raw.get("overall_confidence")
               or raw.get("overallConfidence") or raw.get("value") or 75)

    # Already numeric
    if isinstance(raw, (int, float)):
        score = float(raw)
        return score * 100 if score <= 1.0 else min(score, 100.0)

    # String — try to extract a number first
    s = str(raw).strip()
    # Find any number in the string: "High (90%)" -> "90"
    nums = re.findall(r"[\d]+(?:\.\d+)?", s)
    if nums:
        score = float(nums[0])
        return score * 100 if score <= 1.0 else min(score, 100.0)

    # Pure word labels
    lower = s.lower()
    if "high" in lower or "excellent" in lower:
        return 85.0
    if "medium" in lower or "moderate" in lower:
        return 65.0
    if "low" in lower or "poor" in lower:
        return 40.0

    return 75.0


class QueryDecomposition(BaseModel):
    """Supervisor's breakdown of a complex query into sub-tasks."""
    original_query: str = Field(description="The original user query")
    sub_queries: list[str] = Field(description="List of decomposed sub-questions")
    research_type: Literal["factual", "analytical", "comparative", "exploratory"] = Field(
        description="Type of research required"
    )
    estimated_complexity: Literal["low", "medium", "high"] = Field(
        description="Estimated complexity of the research task"
    )
    priority_order: list[int] = Field(
        description="Order in which sub-queries should be addressed (indices)"
    )

    @model_validator(mode="before")
    @classmethod
    def normalize_llm_keys(cls, data):
        """Accept common LLM key variants while keeping the internal schema stable."""
        if not isinstance(data, dict):
            return data

        normalized = dict(data)

        if "original_query" not in normalized and "query" in normalized:
            normalized["original_query"] = normalized["query"]

        if "estimated_complexity" not in normalized and "complexity" in normalized:
            normalized["estimated_complexity"] = normalized["complexity"]

        # Normalise estimated_complexity to allowed values
        raw_complexity = str(normalized.get("estimated_complexity", "medium")).lower()
        if raw_complexity not in ("low", "medium", "high"):
            normalized["estimated_complexity"] = "medium"
        else:
            normalized["estimated_complexity"] = raw_complexity

        # Normalise research_type to allowed values
        if "research_type" in normalized:
            raw_rt = str(normalized["research_type"]).lower()
            if raw_rt not in ("factual", "analytical", "comparative", "exploratory"):
                normalized["research_type"] = "exploratory"
        else:
            normalized["research_type"] = "exploratory"

        if "sub_queries" not in normalized:
            raw_sub_queries = (
                normalized.get("sub_questions")
                or normalized.get("subqueries")
                or normalized.get("questions")
            )
            if raw_sub_queries:
                normalized["sub_queries"] = [
                    item.get("question", "") if isinstance(item, dict) else str(item)
                    for item in raw_sub_queries
                ]

        if "priority_order" not in normalized and normalized.get("sub_queries"):
            normalized["priority_order"] = list(range(len(normalized["sub_queries"])))
        elif "priority_order" in normalized:
            raw_po = normalized["priority_order"]
            if isinstance(raw_po, list):
                coerced = []
                for i, item in enumerate(raw_po):
                    # Item may be an int already, or a string sub-query text, or a dict
                    if isinstance(item, int):
                        coerced.append(item)
                    else:
                        # Can't parse string sub-query as int — just use positional index
                        coerced.append(i)
                normalized["priority_order"] = coerced
            else:
                # Completely wrong type — regenerate from sub_queries length
                sq = normalized.get("sub_queries", [])
                normalized["priority_order"] = list(range(len(sq)))

        return normalized


class ResearchFinding(BaseModel):
    """A single research finding from the Researcher agent."""
    claim: str = Field(description="The factual claim or finding")
    source_url: str | None = Field(default=None, description="Source URL if available")
    source_title: str | None = Field(default=None, description="Title of the source")
    confidence: float = Field(ge=0, le=1, description="Confidence score 0-1")
    retrieved_at: datetime = Field(default_factory=datetime.utcnow)
    raw_excerpt: str | None = Field(default=None, description="Raw text excerpt from source")


class ResearcherOutput(BaseModel):
    """Complete output from the Researcher agent."""
    sub_query: str = Field(description="The sub-query being addressed")
    findings: list[ResearchFinding] = Field(description="List of research findings")
    search_queries_used: list[str] = Field(description="Search queries executed")
    sources_consulted: int = Field(description="Number of sources consulted")

    @model_validator(mode="before")
    @classmethod
    def normalize_llm_keys(cls, data):
        """Coerce common LLM output variants into the expected schema.

        The LLM sometimes returns a flat single-finding object instead of the
        nested ResearcherOutput structure.  We detect that case and wrap it.
        """
        if not isinstance(data, dict):
            return data

        normalized = dict(data)

        # --- sub_query aliases ---
        if "sub_query" not in normalized:
            normalized["sub_query"] = (
                normalized.get("query")
                or normalized.get("sub_question")
                or normalized.get("question")
                or "Unknown sub-query"
            )

        # --- findings: handle flat single-finding object ---
        if "findings" not in normalized:
            # LLM returned a flat object with claim/sources at the top level
            if "claim" in normalized:
                raw_sources = normalized.get("sources", [])
                findings = []
                if raw_sources:
                    for src in raw_sources:
                        findings.append({
                            "claim": normalized["claim"],
                            "source_url": src.get("url"),
                            "source_title": src.get("title"),
                            "confidence": normalized.get("confidence", 0.7),
                            "raw_excerpt": src.get("excerpt") or src.get("snippet"),
                        })
                else:
                    findings.append({
                        "claim": normalized["claim"],
                        "source_url": None,
                        "source_title": None,
                        "confidence": normalized.get("confidence", 0.7),
                        "raw_excerpt": None,
                    })
                normalized["findings"] = findings
            else:
                normalized["findings"] = []

        # Normalise each finding: handle 'sources' list inside a finding dict
        coerced_findings = []
        for f in normalized.get("findings", []):
            if not isinstance(f, dict):
                coerced_findings.append(f)
                continue
            if "claim" not in f:
                f = dict(f)
                f["claim"] = str(f)
            # Flatten nested sources list into the first source's url/title
            if "sources" in f and isinstance(f["sources"], list) and f["sources"]:
                first = f["sources"][0]
                f.setdefault("source_url", first.get("url"))
                f.setdefault("source_title", first.get("title"))
                f.setdefault("raw_excerpt", first.get("excerpt") or first.get("snippet"))
            coerced_findings.append(f)
        normalized["findings"] = coerced_findings

        # --- search_queries_used ---
        if "search_queries_used" not in normalized:
            normalized["search_queries_used"] = (
                normalized.get("search_queries")
                or normalized.get("queries_used")
                or [normalized["sub_query"]]
            )

        # --- sources_consulted ---
        if "sources_consulted" not in normalized:
            raw = normalized.get("sources_count") or normalized.get("num_sources")
            if raw is not None:
                normalized["sources_consulted"] = int(raw)
            else:
                # Count from findings if not provided
                normalized["sources_consulted"] = len(normalized.get("findings", []))

        return normalized


class CriticFeedback(BaseModel):
    """Critic agent's evaluation of research findings."""
    finding_index: int = Field(description="Index of the finding being critiqued")
    issues: list[str] = Field(description="List of identified issues")
    severity: Literal["minor", "moderate", "critical"] = Field(
        description="Severity of issues found"
    )
    suggestions: list[str] = Field(description="Suggestions for improvement")
    requires_revision: bool = Field(description="Whether this finding needs revision")

    @model_validator(mode="before")
    @classmethod
    def normalize_llm_keys(cls, data):
        if not isinstance(data, dict):
            return data
        d = dict(data)
        if "finding_index" not in d:
            d["finding_index"] = int(d.get("id", 0))
        if "issues" not in d:
            raw = d.get("problems") or d.get("weaknesses") or []
            if isinstance(raw, list):
                d["issues"] = [
                    (i.get("description") or i.get("type") or str(i)) if isinstance(i, dict) else str(i)
                    for i in raw
                ]
            else:
                d["issues"] = []
        if "suggestions" not in d:
            raw = d.get("recommendations") or d.get("improvements") or []
            if isinstance(raw, list):
                d["suggestions"] = [
                    (s.get("description") or s.get("type") or str(s)) if isinstance(s, dict) else str(s)
                    for s in raw
                ]
            else:
                d["suggestions"] = []
        if "severity" not in d:
            d["severity"] = "minor"
        if "requires_revision" not in d:
            d["requires_revision"] = d.get("severity") in ("moderate", "critical")
        return d


class CriticOutput(BaseModel):
    """Complete output from the Critic agent."""
    overall_assessment: Literal["acceptable", "needs_work", "major_issues"] = Field(
        description="Overall assessment of the research"
    )
    feedback_items: list[CriticFeedback] = Field(description="Detailed feedback per finding")
    red_flags: list[str] = Field(description="Critical issues that must be addressed")
    strengths: list[str] = Field(description="Strong points of the research")

    @model_validator(mode="before")
    @classmethod
    def normalize_llm_keys(cls, data):
        if not isinstance(data, dict):
            return data
        d = dict(data)

        # Unwrap nested wrapper key like {"evaluation": {...}}
        if len(d) == 1:
            inner = next(iter(d.values()))
            if isinstance(inner, dict):
                d = inner

        # overall_assessment: may be a dict like {"severity": "minor", "summary": "..."}
        if "overall_assessment" not in d:
            raw = d.get("overall") or d.get("assessment") or d.get("verdict") or ""
        else:
            raw = d["overall_assessment"]

        # Resolve if it's a nested object
        if isinstance(raw, dict):
            severity = str(raw.get("severity") or "").lower()
            summary = str(raw.get("summary") or "").lower()
            combined = severity + " " + summary
            if "major" in combined or "critical" in combined:
                d["overall_assessment"] = "major_issues"
            elif "moderate" in combined or "needs" in combined or "work" in combined:
                d["overall_assessment"] = "needs_work"
            else:
                d["overall_assessment"] = "acceptable"
        elif isinstance(raw, str):
            raw_lower = raw.lower()
            if "major" in raw_lower or "critical" in raw_lower:
                d["overall_assessment"] = "major_issues"
            elif "needs" in raw_lower or "work" in raw_lower or "improve" in raw_lower or "moderate" in raw_lower:
                d["overall_assessment"] = "needs_work"
            else:
                d["overall_assessment"] = "acceptable"

        if "feedback_items" not in d:
            raw_items = d.get("feedback") or d.get("critiques") or d.get("evaluations") or []
            # LLM sometimes nests findings inside sub_queries list
            if not raw_items:
                sub_queries = d.get("sub_queries") or []
                for i, sq in enumerate(sub_queries):
                    if isinstance(sq, dict):
                        for finding in sq.get("findings", []):
                            raw_items.append({
                                "finding_index": i,
                                "issues": [
                                    iss.get("description", "") if isinstance(iss, dict) else str(iss)
                                    for iss in finding.get("issues", [])
                                ],
                                "suggestions": [
                                    s.get("description", "") if isinstance(s, dict) else str(s)
                                    for s in finding.get("suggestions", [])
                                ],
                                "severity": "minor",
                                "requires_revision": False,
                            })
            # LLM sometimes returns a flat evaluation dict with section keys
            if not raw_items and isinstance(d.get("evaluation") or {}, dict):
                eval_dict = d.get("evaluation") or {}
                for section_key, section_val in eval_dict.items():
                    if section_key in ("overall_assessment", "recommendations"):
                        continue
                    if isinstance(section_val, dict):
                        raw_items.append({
                            "finding_index": 0,
                            "issues": section_val.get("issues") or [],
                            "suggestions": section_val.get("suggestions") or [],
                            "severity": section_val.get("severity") or "minor",
                            "requires_revision": section_val.get("severity") in ("moderate", "critical"),
                        })
            d["feedback_items"] = raw_items

        if "red_flags" not in d:
            recs = d.get("recommendations") or {}
            if isinstance(recs, dict):
                additional = recs.get("additional_research") or []
                d["red_flags"] = [str(r) for r in additional] if additional else []
            else:
                d["red_flags"] = d.get("critical_issues") or d.get("major_issues") or []

        if "strengths" not in d:
            d["strengths"] = d.get("positives") or d.get("strong_points") or []

        return d


class VerificationResult(BaseModel):
    """Result of verifying a single claim."""
    claim: str = Field(description="The claim being verified")
    verified: bool = Field(description="Whether the claim could be verified")
    confidence: float = Field(ge=0, le=1, description="Verification confidence")
    supporting_sources: list[str] = Field(description="URLs of supporting sources")
    contradicting_sources: list[str] = Field(description="URLs of contradicting sources")
    verification_notes: str | None = Field(default=None)

    @model_validator(mode="before")
    @classmethod
    def normalize_llm_keys(cls, data):
        if not isinstance(data, dict):
            return data
        d = dict(data)
        if "claim" not in d:
            d["claim"] = d.get("description") or d.get("statement") or str(d)
        if "verified" not in d:
            d["verified"] = bool(d.get("is_verified") or d.get("confirmed") or False)
        if "confidence" not in d:
            raw = d.get("confidence_score") or d.get("score") or 0.8
            d["confidence"] = float(raw) / 100 if float(raw) > 1 else float(raw)
        if "supporting_sources" not in d:
            d["supporting_sources"] = d.get("supporting_urls") or d.get("sources") or []
        if "contradicting_sources" not in d:
            d["contradicting_sources"] = d.get("contradicting_urls") or []
        # Ensure lists contain strings, not dicts
        d["supporting_sources"] = [
            s.get("url", str(s)) if isinstance(s, dict) else str(s)
            for s in d["supporting_sources"]
        ]
        d["contradicting_sources"] = [
            s.get("url", str(s)) if isinstance(s, dict) else str(s)
            for s in d["contradicting_sources"]
        ]
        return d


class VerifierOutput(BaseModel):
    """Complete output from the Verifier agent."""
    verified_claims: list[VerificationResult] = Field(description="Verification results")
    cross_reference_score: float = Field(
        ge=0, le=100, description="Overall cross-reference score 0-100"
    )
    consensus_level: Literal["strong", "moderate", "weak", "conflicting"] = Field(
        description="Level of source consensus"
    )

    @model_validator(mode="before")
    @classmethod
    def normalize_llm_keys(cls, data):
        if not isinstance(data, dict):
            return data
        d = dict(data)

        if "verified_claims" not in d:
            d["verified_claims"] = (
                d.get("claims")
                or d.get("verification_results")
                or d.get("results")
                or []
            )

        if "cross_reference_score" not in d:
            raw = d.get("overall_score") or d.get("score") or d.get("accuracy_score") or 75
            d["cross_reference_score"] = float(raw)

        if "consensus_level" not in d:
            raw = str(d.get("overall_consensus") or d.get("consensus") or "moderate").lower()
            if "strong" in raw:
                d["consensus_level"] = "strong"
            elif "weak" in raw or "low" in raw:
                d["consensus_level"] = "weak"
            elif "conflict" in raw:
                d["consensus_level"] = "conflicting"
            else:
                d["consensus_level"] = "moderate"

        return d


class CitationCheck(BaseModel):
    """Result of checking a single citation."""
    citation_url: str = Field(description="The URL being checked")
    is_accessible: bool = Field(description="Whether the URL is accessible")
    content_matches_claim: bool | None = Field(
        default=None, description="Whether content supports the claim"
    )
    source_credibility: Literal["high", "medium", "low", "unknown"] = Field(
        description="Assessed credibility of source"
    )

    @model_validator(mode="before")
    @classmethod
    def normalize_llm_keys(cls, data):
        if not isinstance(data, dict):
            return data
        d = dict(data)
        if "citation_url" not in d:
            d["citation_url"] = d.get("url") or d.get("source") or ""
        if "is_accessible" not in d:
            d["is_accessible"] = bool(d.get("accessibility") or d.get("accessible") or True)
        if "content_matches_claim" not in d:
            d["content_matches_claim"] = d.get("content_match") or d.get("matches_claim")
        if "source_credibility" not in d:
            raw = str(d.get("credibility") or d.get("reliability") or "unknown").lower()
            if raw in ("high", "medium", "low", "unknown"):
                d["source_credibility"] = raw
            else:
                d["source_credibility"] = "unknown"
        return d


class FactCheckerOutput(BaseModel):
    """Complete output from the Fact-Checker agent."""
    citation_checks: list[CitationCheck] = Field(description="Results of citation validation")
    factual_accuracy_score: float = Field(
        ge=0, le=100, description="Overall factual accuracy score"
    )
    flagged_claims: list[str] = Field(description="Claims that couldn't be verified")
    recommended_corrections: list[str] = Field(description="Suggested corrections")

    @model_validator(mode="before")
    @classmethod
    def normalize_llm_keys(cls, data):
        if not isinstance(data, dict):
            return data
        d = dict(data)

        if "citation_checks" not in d:
            d["citation_checks"] = (
                d.get("citations")
                or d.get("citation_results")
                or d.get("url_checks")
                or []
            )

        if "factual_accuracy_score" not in d:
            raw = (
                d.get("accuracy_score")
                or d.get("overall_accuracy")
                or d.get("score")
                or 75
            )
            d["factual_accuracy_score"] = float(raw)

        if "flagged_claims" not in d:
            raw = d.get("flags") or d.get("unverified_claims") or d.get("issues") or []
            if isinstance(raw, list):
                d["flagged_claims"] = [
                    (c.get("description") or c.get("claim") or str(c)) if isinstance(c, dict) else str(c)
                    for c in raw
                ]
            else:
                d["flagged_claims"] = []

        if "recommended_corrections" not in d:
            raw = d.get("corrections") or d.get("recommendations") or d.get("suggestions") or []
            if isinstance(raw, list):
                d["recommended_corrections"] = [
                    (c.get("description") or str(c)) if isinstance(c, dict) else str(c)
                    for c in raw
                ]
            else:
                d["recommended_corrections"] = []

        return d


class WriterOutput(BaseModel):
    """Final synthesized output from the Writer agent."""
    title: str = Field(description="Title for the research output")
    summary: str = Field(description="Executive summary")
    main_content: str = Field(description="Main research content in markdown")
    key_findings: list[str] = Field(description="Bullet points of key findings")
    citations: list[str] = Field(description="Formatted citations")
    confidence_score: float = Field(
        ge=0, le=100, description="Overall confidence in the output"
    )
    caveats: list[str] = Field(description="Important caveats and limitations")

    @model_validator(mode="before")
    @classmethod
    def normalize_llm_keys(cls, data):
        if not isinstance(data, dict):
            return data
        d = dict(data)

        try:
            # summary aliases
            if "summary" not in d:
                d["summary"] = d.get("executive_summary") or d.get("summaryExtended") or ""

            # main_content: can be a nested dict or list — flatten to markdown string
            raw_mc = d.get("main_content") or d.get("mainContent") or d.get("content") or d.get("body") or ""
            if isinstance(raw_mc, dict):
                parts = []
                for section_key, section_val in raw_mc.items():
                    heading = section_key.replace("_", " ").replace("-", " ").title()
                    parts.append(f"## {heading}\n\n{section_val}")
                raw_mc = "\n\n".join(parts)
            elif isinstance(raw_mc, list):
                # List of section objects like [{"theme": "...", "content": "..."}]
                parts = []
                for item in raw_mc:
                    if isinstance(item, dict):
                        heading = item.get("theme") or item.get("title") or item.get("section") or ""
                        body = item.get("content") or item.get("text") or item.get("body") or str(item)
                        parts.append(f"## {heading}\n\n{body}" if heading else body)
                    else:
                        parts.append(str(item))
                raw_mc = "\n\n".join(parts)
            d["main_content"] = str(raw_mc)

            # key_findings: camelCase or other aliases
            if "key_findings" not in d:
                raw_kf = d.get("keyFindings") or d.get("key_takeaways") or []
                if isinstance(raw_kf, list):
                    d["key_findings"] = [
                        (item.get("finding") or item.get("text") or str(item)) if isinstance(item, dict) else str(item)
                        for item in raw_kf
                    ]
                else:
                    d["key_findings"] = []
            else:
                # Ensure every item is a string
                d["key_findings"] = [
                    (item.get("finding") or item.get("text") or str(item)) if isinstance(item, dict) else str(item)
                    for item in (d["key_findings"] if isinstance(d["key_findings"], list) else [])
                ]

            # citations: normalise list of dicts → list of strings
            raw_cit = d.get("citations") or []
            coerced_cit = []
            for c in raw_cit:
                if isinstance(c, str):
                    coerced_cit.append(c)
                elif isinstance(c, dict):
                    url = c.get("url") or c.get("link") or ""
                    title = c.get("title") or c.get("source") or c.get("name") or ""
                    coerced_cit.append(f"[{title}]({url})" if url else title)
                else:
                    coerced_cit.append(str(c))
            d["citations"] = [c for c in coerced_cit if c]

            # confidence_score — resolve from many possible shapes
            # LLM sometimes returns: 90, 0.9, "90%", "High (90%)", {"score": 90}, etc.
            raw_conf = d.get("confidence_score") or d.get("confidenceScore")
            if raw_conf is None:
                ca = d.get("confidence_assessment") or d.get("confidenceAssessment") or {}
                if isinstance(ca, dict):
                    raw_conf = (ca.get("overall_confidence") or ca.get("overallConfidence")
                                or ca.get("score") or ca.get("value"))
            if raw_conf is None:
                raw_conf = d.get("overall_confidence") or d.get("confidence") or 75
            if isinstance(raw_conf, dict):
                raw_conf = (raw_conf.get("overall_confidence") or raw_conf.get("overallConfidence")
                            or raw_conf.get("score") or 75)
            d["confidence_score"] = _parse_confidence(raw_conf)

            # caveats aliases
            raw_cav = d.get("caveats") or d.get("limitations") or d.get("warnings") or d.get("notes") or []
            if isinstance(raw_cav, list):
                d["caveats"] = [
                    (c.get("text") or c.get("description") or str(c)) if isinstance(c, dict) else str(c)
                    for c in raw_cav
                ]
            else:
                d["caveats"] = []

        except Exception as exc:
            import traceback as _tb
            _tb.print_exc()
            raise ValueError(f"WriterOutput normalization failed: {exc}") from exc

        return d


class AgentMessage(BaseModel):
    """Message passed between agents."""
    sender: str = Field(description="Name of the sending agent")
    receiver: str = Field(description="Name of the receiving agent")
    message_type: Literal["task", "result", "feedback", "request"] = Field(
        description="Type of message"
    )
    content: dict = Field(description="Message content")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
