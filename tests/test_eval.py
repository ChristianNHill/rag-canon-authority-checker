from ragcanon import eval as eval_


def _result(stratum, verdict_correct, needs_review_correct=None, citation_plausible=None):
    return {
        "id": "x", "stratum": stratum, "actual_verdict": "confirmed",
        "expected_verdict": "confirmed", "verdict_correct": verdict_correct,
        "needs_review_correct": needs_review_correct,
        "citation_plausible": citation_plausible,
    }


def test_per_stratum_not_aggregated_together():
    # one stratum all correct, another all wrong -- a single aggregate would
    # average these into a misleadingly middling number
    results = [_result("clean", True), _result("clean", True),
               _result("conflicting", False), _result("conflicting", False)]

    summary = eval_.summarize(results)

    assert summary["clean"]["verdict_accuracy"] == 1.0
    assert summary["conflicting"]["verdict_accuracy"] == 0.0


def test_needs_review_accuracy_ignores_unscored_cases():
    # most cases don't set an expected needs_review (it depends on model
    # confidence, not something independently verifiable) -- those None
    # entries must not count as correct, incorrect, or divide the denominator
    results = [_result("hard_contradiction", True, needs_review_correct=True),
               _result("hard_contradiction", True, needs_review_correct=None)]

    summary = eval_.summarize(results)

    assert summary["hard_contradiction"]["needs_review_accuracy"] == 1.0


def test_citation_plausibility_none_for_not_established():
    # not_established cases have no winning_row/quote to judge
    results = [_result("not_established", True, citation_plausible=None)]

    summary = eval_.summarize(results)

    assert summary["not_established"]["citation_plausibility_rate"] is None


if __name__ == "__main__":
    test_per_stratum_not_aggregated_together()
    test_needs_review_accuracy_ignores_unscored_cases()
    test_citation_plausibility_none_for_not_established()
    print("ok")
