# Testing

## Setup

Install pytest if you haven't already:

```
pip install pytest
```

No API key is needed to run the unit tests. The test suite uses `FakeSponsorDimensionEvaluator`
(in `conftest.py`) to stand in for the Claude backend.

## Running the tests

Run the full test suite from the project root:

```
pytest tests/
```

Run just the sponsor evaluator tests:

```
pytest tests/services/sponsor_evaluator/
```

Run a specific file:

```
pytest tests/services/sponsor_evaluator/test_scoring.py
```

Run tests using sh script

```
sh scripts/docker-checks.sh
```

## What's covered

| File                | What it tests                                              |
| ------------------- | ---------------------------------------------------------- |
| `test_scoring.py`   | `ScoreCalculator` — weighted average math and validation   |
| `test_bridge.py`    | `crawl_to_evidence` — evidence bucketing and deduplication |
| `test_evaluator.py` | `SponsorEvaluator` — orchestration flow, not LLM logic     |

## Testing the full LLM pipeline with a real company

`demo_evaluator.py` runs a full end-to-end evaluation against a real company using
the live Claude API. Use it to manually verify that the LLM layer, prompt formatting,
tool-use parsing, and score assembly all work together correctly.

**Requires** `ANTHROPIC_API_KEY` set in your `.env` (copy `.env.example` and fill it in).

Run it from the project root:

```
python3 tests/demo_evaluator.py
```

It evaluates Shopify by default and prints every field of the resulting `SponsorScore`
— criterion scores with reasoning and supporting evidence, confidence, motivations,
outreach angle, and the full explanation.

To test a different company, edit the `company` and `evidence` blocks near the top of
`demo_evaluator.py`. Use `Evidence` fields as a checklist of what the scraper should
ideally provide — the richer the evidence, the more grounded the scores will be.

## Adding tests for the LLM layer

`test_evaluator.py` only tests orchestration in `evaluator.py`.
To test `ClaudeSponsorDimensionEvaluator` itself you need a real API key —
set `ANTHROPIC_API_KEY` in your `.env` and mark those tests with a custom
`@pytest.mark` so they can be skipped in CI.
