
from sponsor_pipeline.services.sponsor_evaluator.criteria import (
    CRITERIA,
    CRITERIA_BY_KEY,
)


def test_six_criteria_exist():
    assert len(CRITERIA) == 6
    for criterion in CRITERIA:
        assert criterion.key
        assert criterion.name
        assert criterion.description
        assert criterion.weight

def test_criteria_have_real_descriptions():
    for criterion in CRITERIA:
        assert criterion.description.strip()

def test_criteria_have_real_names():
    for criterion in CRITERIA:
        assert criterion.name.strip()

def test_criterion_keys_are_unique():
    keys = [criterion.key for criterion in CRITERIA]
    assert len(keys) == len(set(keys))


def test_all_criteria_have_positive_weights():
    for criterion in CRITERIA:
        assert criterion.weight > 0


def test_criteria_lookup_matches_list():
    assert len(CRITERIA_BY_KEY) == len(CRITERIA)
    keys = {criterion.key for criterion in CRITERIA}
    assert set(CRITERIA_BY_KEY.keys()) == keys


def test_lookup_returns_same_object():
    for criterion in CRITERIA:
        assert CRITERIA_BY_KEY[criterion.key] is criterion
