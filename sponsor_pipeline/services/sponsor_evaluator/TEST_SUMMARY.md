# Sponsor Evaluator Test Summary

---

## Tested layers

### 1. Data Structures `schemas.py` (14 tests)

This file defines the building blocks every other module uses: Company, Evidence, CriterionScore, SponsorScore, and the Confidence , SponsorMotivation enums

**summary:**

- create a `Company` with just a name, the other fields (website, industry, description) safely default to empty strings, so nothing crashes when data is missing

- Every field on `Evidence` defaults to an empty list, not `None`, the prompt builders iterate over these lists, a `None` default would cause a crash

- Each `Evidence` instance gets its own independent list

- The `Confidence` and `SponsorMotivation` enums reject invalid values with a clear error
  ex: if the LLM returns `"High"` instead of `"high"`, the parser fails loudly rather than silently

---

### 2. Evaluation Criteria Configuration `criteria.py` (7 test)

the file defines the six sponsorship dimensions and their weights
(Talent Acquisition, Developer Ecosystem, Community Sponsorship,
Outreach Accessibility, Sponsorship Capacity, Strategic Alignment)

**summary:**

- There are exactly 6 criteria (no accidental additions or removals)

- All criterion keys are unique. a duplicate key would cause one dimension to silently overwrite another in the results dictionary

- All weights are positive, a zero weight would mean a dimension gets scored by the LLM
  (spending tokens & money) but contributes nothing to the final score

- The `CRITERIA_BY_KEY` lookup dictionary is in sync with the `CRITERIA` list

---

### 3. Score Calculation `scoring.py` (15 tests)

the math layer, it takes the six dimension scores and combines them into a single
overall score using a weighted average

**What we confirmed:**

- Equal weights produce a plain average : two scores of 6 and 8 with equal weights gives 7.0

- Unequal weights pull the result toward the heavier dimension, as expected

- A single criterion calculator returns exactly that criterion's score

- Results are rounded to 2 decimal places

- Extra scores that dont match any known criterion are ignored

- Boundary scores of exactly 0.0 and 10.0 are both accepted as valid

- A score above 10.0 or below 0.0 raises a `ValueError`, catching the case where the LLM hallucinates an out-of-range score before corrupting the output

- An empty scores dict raises `ValueError` instead of returning 0 silently

- A calculator where all weights are 0.0 raises `ValueError` to not divide by zero

---

### 4. Prompt Builders `llm/sponsor_dimension_evaluator.py` (12 tests)

the functions that build the text sent to Claude, (company name missing, evidence not included) won't raise an exception, the LLM will just quietly produce lower-quality output

**summary:**

- The company name always appears in the prompt

- The criterion name and what it measures always appear

- The primary evidence for each dimension appears in its dedicated section
  ex: `hiring_signals` is the primary evidence for Talent Acquisition & `developer_products` is the primary evidence for Developer Ecosystem

- When evidence is available --> at least one evidence hint from the criterion is included to guide the LLM's reasoning

- When a primary evidence field is empty, the prompt says `none collected`instead of leaving a blank section that may confuse the model

- Optional company fields (industry, website, description) appear when provided and are removed entirely when empty without blank lines like `"Industry: "` in the prompt

- The summary prompt includes all six dimension scores

---

### 5. Response Parsers `llm/sponsor_dimension_evaluator.py` (11 tests)

they take the raw response from Claude and convert it into a structured Python objects (`CriterionScore` & `SponsorEvaluationSummary`)

**summary:**

- all fields (score, reasoning, supporting evidence) are correctly extracted from the response

- The score is always stored as a float

- `supporting_evidence` defaults to `[]` when the LLM omits it

- The parser correctly finds the tool block even when Claude prefixes it with a plain text block

- If Claude returns no tool block at all, a clear `ValueError` is raised

- Motivation strings like `talent` and confidence strings like `high` are correctly converted into their respective enum types `SponsorMotivation.TALENT`, `Confidence.HIGH`

---

### 6. Orchestration `evaluator.py` (9 tests)

**summary:**

- `evaluate()` always returns a `SponsorScore`

- The LLM evaluator is called exactly 6 times(1 per dimension)

- The criterion keys passed to the evaluator match the six defined criteria

- The overall score is wired to `ScoreCalculator`, With all six dimensions

- The original `Company` object is unchanged in the result

- The `criterion_scores` dictionary in the result contains all thw six keys

- Every field from the summary(motivations, confidence, explanation, strengths, weaknesses, outreach angle, contact role) is assembled into the final output

---

## What's not tested yet

`ClaudeSponsorDimensionEvaluator`, the class that actually
calls the Claude API. requires a real `ANTHROPIC_API_KEY`, this integration test
will be conducted separately once the rest of the pipeline is ready and wired
