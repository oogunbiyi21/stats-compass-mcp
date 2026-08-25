"""The honesty fields must survive the workflow summariser.

summarize_workflow_result trims workflow output to keep responses small. If it
dropped evaluated_on or train_metrics, the assistant would once again see a bare
accuracy number with nothing saying whether it describes held-out data — which is
the condition that let inflated metrics go unnoticed in the first place.
"""

from stats_compass_mcp.workflow_summary import summarize_workflow_result


def _workflow_result(**evaluation):
    return {
        "workflow_name": "run_classification",
        "status": "success",
        "steps": [
            {"step_name": "train_model", "status": "success", "result": {"model_id": "m1"}},
            {"step_name": "evaluate_model", "status": "success", "result": evaluation},
        ],
        "artifacts": {},
    }


def _evaluation_step(summary):
    return next(s for s in summary["steps"] if s["step"] == "evaluate_model")


class TestHonestyFieldsSurvive:
    def test_evaluated_on_is_preserved(self):
        summary = summarize_workflow_result(
            _workflow_result(accuracy=0.69, evaluated_on="test", n_samples=99)
        )
        assert _evaluation_step(summary)["result"]["evaluated_on"] == "test"

    def test_train_metrics_are_preserved(self):
        """Without the gap, an overfitted model is indistinguishable from a good one."""
        summary = summarize_workflow_result(
            _workflow_result(
                accuracy=0.69,
                evaluated_on="test",
                train_metrics={"accuracy": 1.0, "n_samples": 395},
            )
        )
        train = _evaluation_step(summary)["result"]["train_metrics"]
        assert train["accuracy"] == 1.0

    def test_sample_count_is_preserved(self):
        summary = summarize_workflow_result(
            _workflow_result(accuracy=0.69, evaluated_on="test", n_samples=99)
        )
        assert _evaluation_step(summary)["result"]["n_samples"] == 99
