"""
LLM backed evaluator for individual sponsorship dimensions
This module owns all prompt engineering and LLM interaction logic,
evaluator.py calls into this module and receives structured results back
rather than touching a prompt string directly

The abstract class SponsorDimensionEvaluator is the contract evaluator.py depends on.
Three concrete implementations live here, one per supported LLM provider:
    - ClaudeSponsorDimensionEvaluator   (Anthropic)
    - OpenAISponsorDimensionEvaluator   (OpenAI)
    - GoogleSponsorDimensionEvaluator   (Google / Gemini)

all three share the same prompts and tool schemas defined at module level below
the only thing that differs per provider is how the API call is made and how
the response is parsed, the actual content is identical

Structured output (tool / function calling):
    define a "tool" whose input schema matches the data we need, then force
    the model to call it. This guarantees the response arrives as validated JSON
    instead of free-form text we'd have to parse, each provider calls
    this feature slightly different (tools / functions) but the idea
    is the same everywhere
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass

from sponsor_pipeline.services.sponsor_evaluator.criteria import EvaluationCriterion
from sponsor_pipeline.services.sponsor_evaluator.schemas import (
    Company,
    Confidence,
    CriterionScore,
    Evidence,
    SponsorMotivation,
)

# ---------------------------------------------------------------------------
# Summary result  produced  after all  criterion scores are collected
# ---------------------------------------------------------------------------


@dataclass
class SponsorEvaluationSummary:
    """
    evaluation fields that require looking across all six criteria
    Produced by an LLM call after individual dimension scores are known
    """

    motivations: list[SponsorMotivation]
    """Why this company would sponsor, may. be more than one factor"""

    confidence: Confidence
    """How well-supported the evaluation is given the available evidence"""

    explanation: str
    """Short paragraph summarising the overall evaluation for a human reader"""

    key_strengths: list[str]
    """The strongest reasons this company is worth pursuing"""

    potential_weaknesses: list[str]
    """Risks or gaps that may make this company harder to close"""

    recommended_outreach_angle: str
    """The specific pitch angle most likely to resonate with this company"""

    recommended_contact_role: str
    """Job title or role at this company most likely to own the sponsorship decision"""


# ---------------------------------------------------------------------------
# Abstract interface, evaluator.py depends on this, not on any concrete impl
# ---------------------------------------------------------------------------


class SponsorDimensionEvaluator(ABC):
    """
    the contract between evaluator.py and the LLM layer
    Concrete implementations live in this module and handle prompt construction,
    LLM calls, response parsing. evaluator.py just calls the two methods
    evaluate_dimension and evaluate_summary.
    """

    @abstractmethod
    def evaluate_dimension(
        self,
        criterion: EvaluationCriterion,
        company: Company,
        evidence: Evidence,
    ) -> CriterionScore:
        """
        called per-dimension to score a single sponsorship dimension for the given company
        Args:
            criterion:  The dimension to evaluate (from criteria.py)
            company:    Basic company metadata
            evidence:   Structured facts collected during earlier discovery stage
        Returns:
            A CriterionScore with score (0–10) along with reasoning, and supporting evidence
        """

    @abstractmethod
    def evaluate_summary(
        self,
        company: Company,
        evidence: Evidence,
        criterion_scores: dict[str, CriterionScore],
    ) -> SponsorEvaluationSummary:
        """
        called once, it produces holistic evaluation fields after all  dimensions are scored
        Args:
            company:          Basic company metadata
            evidence:         Structured facts collected during discovery (scraping)
            criterion_scores: All six CriterionScore results keyed by criterion_key
        Returns:
            A SponsorEvaluationSummary with confidence, motivations, outreach advice...
        """


# ---------------------------------------------------------------------------
# Shared system prompts
# defined at module level so all three provider classes use the same wording
# what the LLM is told lives here
# ---------------------------------------------------------------------------

_DIMENSION_SYSTEM_PROMPT = (
    "You are a sponsorship analyst for Hack Canada, a major Canadian university hackathon.\n"
    "Your job is to score one dimension of a company's fit as a potential sponsor.\n"
    "\n"
    "Rules:\n"
    "- Score based only on the evidence provided, never on company reputation or name recognition\n"
    "- A well-known company with no relevant evidence should score low\n"
    "- A smaller company with strong targeted evidence should score high\n"
    "- Cite the specific evidence items that drove the score in supporting_evidence"
)

_SUMMARY_SYSTEM_PROMPT = (
    "You are a sponsorship analyst for Hack Canada, a major Canadian university hackathon.\n"
    "You have already scored a company across six dimensions. Now produce a holistic summary.\n"
    "\n"
    "Rules:\n"
    "- Motivations must be grounded in the dimension scores and evidence, not assumed\n"
    "- Confidence reflects evidence volume and quality, not score height\n"
    "- The outreach angle should be concrete and specific to this company, not generic\n"
    "- Recommended contact role should be a real job title, not a vague category"
)


# ---------------------------------------------------------------------------
# Shared evidence field metadata
# These tell the prompt builders which evidence field maps to which criterion,
# and what human-readable label to attach to each field in the prompt
# ---------------------------------------------------------------------------

# Maps each criterion key to the Evidence field that carries its primary signals
# For this evaluation criterion, which evidence is the most important?
# it chooses what to emphasize for each criterion

_PRIMARY_EVIDENCE_FIELD: dict[str, str] = {
    "talent_acquisition": "hiring_signals",
    "developer_ecosystem": "developer_products",
    "community_sponsorship": "past_sponsorships",
    "outreach_accessibility": "contact_signals",
    "sponsorship_capacity": "company_size_signals",
    "strategic_alignment": "canada_signals",
}

# All evidence fields with human-readable labels
# used by both the dimension and summary prompt builders
_EVIDENCE_FIELDS: list[tuple[str, str]] = [
    ("hiring_signals", "Hiring signals"),
    ("developer_products", "Developer products"),
    ("past_sponsorships", "Past sponsorships"),
    ("contact_signals", "Contact signals"),
    ("company_size_signals", "Company size signals"),
    ("canada_signals", "Canada signals"),
]


# ---------------------------------------------------------------------------
# Shared prompt builders
# These are plain functions (not tied to any class) cuz all three provider
# classes call them, The prompts are completely provider-agnostic
# ---------------------------------------------------------------------------


def _build_dimension_prompt(
    criterion: EvaluationCriterion,
    company: Company,
    evidence: Evidence,
) -> str:
    """Build the user-turn message for a single dimension evaluation."""
    lines: list[str] = [f"Company: {company.name}"]
    if company.industry:
        lines.append(f"Industry: {company.industry}")
    if company.website:
        lines.append(f"Website: {company.website}")
    if company.description:
        lines.append(f"Description: {company.description}")

    lines += [
        "",
        f"Criterion to evaluate: {criterion.name}",
        f"What this measures: {criterion.description}",
        "",
        "Evidence hints (what to look for):",
    ]
    for hint in criterion.evidence_hints:
        lines.append(f"  - {hint}")

    # primary evidence: the field that maps directly to this criterion
    primary_field = _PRIMARY_EVIDENCE_FIELD.get(criterion.key, "")
    primary_items = getattr(evidence, primary_field, []) if primary_field else []

    lines += ["", "Primary evidence (directly relevant to this criterion):"]
    if primary_items:
        for item in primary_items:
            lines.append(f"  - {item}")
    else:
        lines.append("  (none collected)")

    # supporting context: all other evidence fields
    other_fields = [(f, label) for f, label in _EVIDENCE_FIELDS if f != primary_field]
    has_other = any(getattr(evidence, f, []) for f, _ in other_fields)

    lines += ["", "Additional context (all other collected evidence):"]
    if has_other:
        for field, label in other_fields:
            items = getattr(evidence, field, [])
            if items:
                lines.append(f"  {label}:")
                for item in items:
                    lines.append(f"    - {item}")
    else:
        lines.append("  (none)")

    lines += [
        "",
        f"Score {company.name!r} on '{criterion.name}' from 0.0 to 10.0.",
        "Base the score strictly on the evidence above, not on company reputation.",
    ]

    return "\n".join(lines)


def _build_summary_prompt(
    company: Company,
    evidence: Evidence,
    criterion_scores: dict[str, CriterionScore],
) -> str:
    """Build the user-turn message for the holistic summary call."""
    lines: list[str] = [f"Company: {company.name}"]
    if company.industry:
        lines.append(f"Industry: {company.industry}")
    if company.website:
        lines.append(f"Website: {company.website}")
    if company.description:
        lines.append(f"Description: {company.description}")

    lines += ["", "All collected evidence:"]
    has_evidence = False
    for field, label in _EVIDENCE_FIELDS:
        items = getattr(evidence, field, [])
        if items:
            has_evidence = True
            lines.append(f"  {label}:")
            for item in items:
                lines.append(f"    - {item}")
    if not has_evidence:
        lines.append("  (none collected)")

    lines += ["", "Dimension scores already computed:"]
    for key, cs in criterion_scores.items():
        lines.append(f"  {key}: {cs.score}/10  — {cs.reasoning}")

    lines += [
        "",
        "Produce a holistic evaluation summary using all the information above.",
        "Confidence should reflect evidence volume and quality, not how high the scores are.",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Shared tool schemas
# These define the JSON shape expected back from the LLM
# They are plain dicts in JSON Schema format, for Anthropic : "tools", OpenAI : "functions",
# Google : "function declarations" (schema content is identical)
# ---------------------------------------------------------------------------
def _criterion_score_tool() -> dict:
    """
    tool schema that forces the LLM to return a structured CriterionScore,
    the LLM populates all required fields before responding, so the output
    arrives as validated JSON to be parsed into a CriterionScore object
    """
    return {
        "name": "record_criterion_score",
        "description": (
            "Record the evaluation score for a single sponsorship criterion. "
            "Call this tool once with your final assessment."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "score": {
                    "type": "number",
                    "description": "Score from 0.0 to 10.0 based on the available evidence",
                },
                "reasoning": {
                    "type": "string",
                    "description": "One to three sentences explaining why this score was assigned",
                },
                "supporting_evidence": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "The specific evidence items from the prompt that justify the score",
                },
            },
            "required": ["score", "reasoning", "supporting_evidence"],
        },
    }


def _summary_tool() -> dict:
    """
    schema that forces the LLM to return a structured SponsorEvaluationSummary
    """
    return {
        "name": "record_evaluation_summary",
        "description": (
            "Record the holistic evaluation summary after all six criteria have been scored. "
            "Call this tool once with the complete summary."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "motivations": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["talent", "developer_adoption", "brand_awareness"],
                    },
                    "description": "Primary reasons this company would sponsor Hack Canada",
                },
                "confidence": {
                    "type": "string",
                    "enum": ["low", "medium", "high"],
                    "description": "How well-supported this evaluation is given the available evidence",
                },
                "explanation": {
                    "type": "string",
                    "description": "Short paragraph summarising the overall evaluation for a human reader",
                },
                "key_strengths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "The strongest reasons this company is worth pursuing",
                },
                "potential_weaknesses": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Risks or gaps that may make this company harder to close",
                },
                "recommended_outreach_angle": {
                    "type": "string",
                    "description": "The specific pitch angle most likely to resonate with this company",
                },
                "recommended_contact_role": {
                    "type": "string",
                    "description": "Job title or role at this company most likely to own the sponsorship decision",
                },
            },
            "required": [
                "motivations",
                "confidence",
                "explanation",
                "key_strengths",
                "potential_weaknesses",
                "recommended_outreach_angle",
                "recommended_contact_role",
            ],
        },
    }


# ---------------------------------------------------------------------------
# Claude implementation
# Uses Anthropic's tool_choice to force a tool_use block in the response
# ---------------------------------------------------------------------------
class ClaudeSponsorDimensionEvaluator(SponsorDimensionEvaluator):
    """
    Claude backed implementation of SponsorDimensionEvaluator
    """

    def __init__(
        self,
        client,  # anthropic.Anthropic instance, injected by the orchestrator
        model: str = "claude-sonnet-4-6",
    ) -> None:
        self._client = client
        self._model = model

    def evaluate_dimension(
        self,
        criterion: EvaluationCriterion,
        company: Company,
        evidence: Evidence,
    ) -> CriterionScore:
        tool = _criterion_score_tool()
        response = self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            system=_DIMENSION_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": _build_dimension_prompt(criterion, company, evidence),
                }
            ],
            tools=[tool],
            # Forcing the model to call this specific tool guarantees a tool_use block
            tool_choice={"type": "tool", "name": tool["name"]},
        )
        return _parse_claude_criterion_score(criterion.key, response)

    def evaluate_summary(
        self,
        company: Company,
        evidence: Evidence,
        criterion_scores: dict[str, CriterionScore],
    ) -> SponsorEvaluationSummary:
        tool = _summary_tool()
        response = self._client.messages.create(
            model=self._model,
            max_tokens=2048,
            system=_SUMMARY_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": _build_summary_prompt(
                        company, evidence, criterion_scores
                    ),
                }
            ],
            tools=[tool],
            # force the tool call so we always get structured JSON back
            tool_choice={"type": "tool", "name": tool["name"]},
        )
        return _parse_claude_summary(response)


def _parse_motivations(raw: list) -> list[SponsorMotivation]:
    """
    Convert raw motivation strings to SponsorMotivation enums, skipping any
    invalid values the LLM may return (ex: criterion keys instead of motivation values)
    """
    result = []
    for m in raw:
        try:
            result.append(SponsorMotivation(m))
        except ValueError:
            pass
    return result or [SponsorMotivation.BRAND_AWARENESS]


def _parse_claude_criterion_score(criterion_key: str, response) -> CriterionScore:
    """
    Extracts the tool_use block from a Claude dimension response
    """
    tool_block = next(
        (block for block in response.content if block.type == "tool_use"),
        None,
    )
    if tool_block is None:
        raise ValueError(
            f"Claude did not return a tool_use block for criterion '{criterion_key}'. "
            f"Response stop reason: {response.stop_reason!r}"
        )
    data = tool_block.input
    return CriterionScore(
        criterion_key=criterion_key,
        score=float(data["score"]),
        reasoning=data["reasoning"],
        supporting_evidence=data.get("supporting_evidence", []),
    )


def _parse_claude_summary(response) -> SponsorEvaluationSummary:
    """
    Extracts the tool_use block from a Claude summary response
    """
    tool_block = next(
        (block for block in response.content if block.type == "tool_use"),
        None,
    )
    if tool_block is None:
        raise ValueError(
            "Claude did not return a tool_use block for the evaluation summary. "
            f"Response stop reason: {response.stop_reason!r}"
        )
    data = tool_block.input
    return SponsorEvaluationSummary(
        motivations=_parse_motivations(data["motivations"]),
        confidence=Confidence(data["confidence"]),
        explanation=data["explanation"],
        key_strengths=data["key_strengths"],
        potential_weaknesses=data["potential_weaknesses"],
        recommended_outreach_angle=data["recommended_outreach_angle"],
        recommended_contact_role=data["recommended_contact_role"],
    )


# ---------------------------------------------------------------------------
# OpenAI implementation
# Uses Openai's function calling (tool_choice) to force a structured response
# ---------------------------------------------------------------------------


class OpenAISponsorDimensionEvaluator(SponsorDimensionEvaluator):
    """
    OpenAI backed implementation of SponsorDimensionEvaluator
    """

    def __init__(
        self,
        client,  #  openai.OpenAI instance, injected by the orchestrator
        model: str = "gpt-4o-mini",
    ) -> None:
        self._client = client
        self._model = model

    def evaluate_dimension(
        self,
        criterion: EvaluationCriterion,
        company: Company,
        evidence: Evidence,
    ) -> CriterionScore:
        tool = _criterion_score_tool()
        response = self._client.chat.completions.create(
            model=self._model,
            max_tokens=1024,
            messages=[
                {"role": "system", "content": _DIMENSION_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": _build_dimension_prompt(criterion, company, evidence),
                },
            ],
            # OpenAI wraps our schema in a "function" (the schema content is the same)
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool["description"],
                        "parameters": tool["input_schema"],
                    },
                }
            ],
            # Force this specific function to be called
            tool_choice={"type": "function", "function": {"name": tool["name"]}},
        )
        return _parse_openai_criterion_score(criterion.key, response)

    def evaluate_summary(
        self,
        company: Company,
        evidence: Evidence,
        criterion_scores: dict[str, CriterionScore],
    ) -> SponsorEvaluationSummary:
        tool = _summary_tool()
        response = self._client.chat.completions.create(
            model=self._model,
            max_tokens=2048,
            messages=[
                {"role": "system", "content": _SUMMARY_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": _build_summary_prompt(
                        company, evidence, criterion_scores
                    ),
                },
            ],
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool["description"],
                        "parameters": tool["input_schema"],
                    },
                }
            ],
            tool_choice={"type": "function", "function": {"name": tool["name"]}},
        )
        return _parse_openai_summary(response)


def _parse_openai_criterion_score(criterion_key: str, response) -> CriterionScore:
    """
    Extracts the function call from an OpenAI dimension response
    OpenAI gives us a JSON string unlike Claude which gives us a dict directly
    """
    choice = response.choices[0]
    if not choice.message.tool_calls:
        raise ValueError(
            f"OpenAI did not return a function call for criterion '{criterion_key}'. "
            f"Finish reason: {choice.finish_reason!r}"
        )
    data = json.loads(choice.message.tool_calls[0].function.arguments)
    return CriterionScore(
        criterion_key=criterion_key,
        score=float(data["score"]),
        reasoning=data["reasoning"],
        supporting_evidence=data.get("supporting_evidence", []),
    )


def _parse_openai_summary(response) -> SponsorEvaluationSummary:
    """
    Extracts the function call from an OpenAI summary response and parses it
    into a SponsorEvaluationSummary
    """
    choice = response.choices[0]
    if not choice.message.tool_calls:
        raise ValueError(
            "OpenAI did not return a function call for the evaluation summary. "
            f"Finish reason: {choice.finish_reason!r}"
        )
    data = json.loads(choice.message.tool_calls[0].function.arguments)
    return SponsorEvaluationSummary(
        motivations=_parse_motivations(data["motivations"]),
        confidence=Confidence(data["confidence"]),
        explanation=data["explanation"],
        key_strengths=data["key_strengths"],
        potential_weaknesses=data["potential_weaknesses"],
        recommended_outreach_angle=data["recommended_outreach_angle"],
        recommended_contact_role=data["recommended_contact_role"],
    )


# ---------------------------------------------------------------------------
# Google / Gemini implementation
# Uses the new google.genai SDK (google-genai package).
# The old google.generativeai package is fully deprecated — no more updates or bug fixes.
# ---------------------------------------------------------------------------
class GoogleSponsorDimensionEvaluator(SponsorDimensionEvaluator):
    """
    Google / Gemini backed implementation of SponsorDimensionEvaluator.
    Uses google.genai (new SDK) — NOT google.generativeai (deprecated).

    How it forces structured output:
        tool_config with mode=ANY and allowed_function_names=[tool_name] tells
        Gemini it must call that specific function. The result arrives as a
        function_call object on the response candidate's content parts.

    Note on schema format:
        The new SDK requires typed types.Schema objects — plain dicts are no longer
        accepted. _json_schema_to_genai_schema() converts our JSON Schema dicts
        into the typed objects the SDK expects, so we don't duplicate schema definitions.

    The client (google.genai.Client) is injected by the orchestrator with the API key
    already set, so we don't touch credentials here.
    """

    def __init__(
        self,
        client,  # google.genai.Client instance, injected by the orchestrator
        model: str = "gemini-2.0-flash",
    ) -> None:
        self._client = client
        self._model = model

    def evaluate_dimension(
        self,
        criterion: EvaluationCriterion,
        company: Company,
        evidence: Evidence,
    ) -> CriterionScore:
        from google.genai import types

        tool_schema = _criterion_score_tool()
        response = self._client.models.generate_content(
            model=self._model,
            contents=_build_dimension_prompt(criterion, company, evidence),
            config=types.GenerateContentConfig(
                system_instruction=_DIMENSION_SYSTEM_PROMPT,
                tools=[_to_genai_tool(tool_schema)],
                # mode ANY + allowed_function_names forces Gemini to call this specific function
                tool_config=types.ToolConfig(
                    function_calling_config=types.FunctionCallingConfig(
                        mode="ANY",
                        allowed_function_names=[tool_schema["name"]],
                    )
                ),
            ),
        )
        return _parse_google_criterion_score(criterion.key, response)

    def evaluate_summary(
        self,
        company: Company,
        evidence: Evidence,
        criterion_scores: dict[str, CriterionScore],
    ) -> SponsorEvaluationSummary:
        from google.genai import types

        tool_schema = _summary_tool()
        response = self._client.models.generate_content(
            model=self._model,
            contents=_build_summary_prompt(company, evidence, criterion_scores),
            config=types.GenerateContentConfig(
                system_instruction=_SUMMARY_SYSTEM_PROMPT,
                tools=[_to_genai_tool(tool_schema)],
                tool_config=types.ToolConfig(
                    function_calling_config=types.FunctionCallingConfig(
                        mode="ANY",
                        allowed_function_names=[tool_schema["name"]],
                    )
                ),
            ),
        )
        return _parse_google_summary(response)


def _to_genai_tool(tool: dict):
    """
    Convert our provider-agnostic tool schema into a google.genai types.Tool object.
    The new SDK requires typed FunctionDeclaration and Schema objects —
    plain dicts are no longer accepted unlike the old google.generativeai SDK.
    """
    from google.genai import types

    return types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name=tool["name"],
                description=tool["description"],
                parameters=_json_schema_to_genai_schema(tool["input_schema"]),
            )
        ]
    )


def _json_schema_to_genai_schema(schema: dict):
    """
    Recursively convert a JSON Schema dict to a google.genai types.Schema object.

    Why we need this:
        Our tool schemas are plain JSON Schema dicts — Anthropic and OpenAI accept
        them directly. The new google.genai SDK requires typed Schema objects instead.
        This function bridges the two formats so we keep one schema definition
        shared across all three providers.

    The conversion is recursive to handle nested properties and array items.
    """
    from google.genai import types

    type_map = {
        "object": types.Type.OBJECT,
        "string": types.Type.STRING,
        "number": types.Type.NUMBER,
        "array": types.Type.ARRAY,
        "integer": types.Type.INTEGER,
    }
    t = type_map.get(schema.get("type", "string"), types.Type.STRING)

    kwargs: dict = {"type": t}
    if "description" in schema:
        kwargs["description"] = schema["description"]
    if "enum" in schema:
        kwargs["enum"] = schema["enum"]
    if "required" in schema:
        kwargs["required"] = schema["required"]
    if "properties" in schema:
        kwargs["properties"] = {
            k: _json_schema_to_genai_schema(v) for k, v in schema["properties"].items()
        }
    if "items" in schema:
        kwargs["items"] = _json_schema_to_genai_schema(schema["items"])

    return types.Schema(**kwargs)


def _extract_google_function_call(response, context: str):
    """
    Find the function_call part in a Google response candidate.
    Gemini puts function calls as parts inside the candidate's content.
    We look for the first part that has a function_call with a non-empty name.
    """
    try:
        part = next(
            p
            for p in response.candidates[0].content.parts
            if hasattr(p, "function_call") and p.function_call.name
        )
        return part.function_call
    except (StopIteration, IndexError, AttributeError):
        raise ValueError(
            f"Google did not return a function call for '{context}'. "
            f"Response: {response!r}"
        )


def _parse_google_criterion_score(criterion_key: str, response) -> CriterionScore:
    """
    Extracts the function call from a Google dimension response and builds a CriterionScore.
    In the new google.genai SDK, function_call.args is already a plain Python dict —
    no proto conversion needed unlike the old google.generativeai SDK.
    """
    fc = _extract_google_function_call(response, criterion_key)
    data = fc.args  # plain dict in the new SDK
    return CriterionScore(
        criterion_key=criterion_key,
        score=float(data["score"]),
        reasoning=data["reasoning"],
        supporting_evidence=list(data.get("supporting_evidence", [])),
    )


def _parse_google_summary(response) -> SponsorEvaluationSummary:
    """
    Extracts the function call from a Google summary response and builds a SponsorEvaluationSummary.
    Same plain dict access as the dimension parser — no proto conversion needed.
    """
    fc = _extract_google_function_call(response, "summary")
    data = fc.args
    return SponsorEvaluationSummary(
        motivations=_parse_motivations(data["motivations"]),
        confidence=Confidence(data["confidence"]),
        explanation=data["explanation"],
        key_strengths=list(data["key_strengths"]),
        potential_weaknesses=list(data["potential_weaknesses"]),
        recommended_outreach_angle=data["recommended_outreach_angle"],
        recommended_contact_role=data["recommended_contact_role"],
    )
