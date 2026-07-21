import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from failure_memory.contracts import PolicyKind, RecoveryPolicy  # noqa: E402
from failure_memory.retrieval import (  # noqa: E402
    Experience,
    FailureQuery,
    SourceBlindTfidfRetriever,
    aggregate_funnel,
    measure_retrieval_funnel,
)


def experience(experience_id: str, source: str, text: str, provenance: str) -> Experience:
    return Experience(
        experience_id=experience_id,
        source_instance_id=source,
        natural_text=text,
        policy=RecoveryPolicy(PolicyKind.RETRY, {"max_attempts": 1}),
        provenance=provenance,
    )


class RetrievalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.experiences = [
            experience("e_retry", "source_a", "tool timeout retry the call once", "timeout"),
            experience(
                "e_stop", "source_b", "authorization denied stop and report", "persistent_authz"
            ),
            experience(
                "e_revise", "source_c", "missing argument revise the field", "argument_error"
            ),
        ]

    def test_source_blind_ranking_is_deterministic_and_excludes_same_source(self) -> None:
        retriever = SourceBlindTfidfRetriever(self.experiences)
        query = FailureQuery("source_a", "timeout while calling tool", "different_hidden_value")
        first = retriever.retrieve(query, top_k=2)
        second = retriever.retrieve(query, top_k=2)
        self.assertEqual(first, second)
        self.assertNotIn("e_retry", [item.experience.experience_id for item in first])

    def test_provenance_does_not_change_source_blind_ranking(self) -> None:
        retriever = SourceBlindTfidfRetriever(self.experiences)
        left = retriever.retrieve(
            FailureQuery("target", "authorization denied", "authz_a"), top_k=2
        )
        right = retriever.retrieve(
            FailureQuery("target", "authorization denied", "authz_b"), top_k=2
        )
        self.assertEqual(left, right)

    def test_funnel_separates_candidate_selected_and_exposed(self) -> None:
        retriever = SourceBlindTfidfRetriever(self.experiences)
        query = FailureQuery("target", "authorization denied", "persistent_authz")
        candidates = retriever.retrieve(query, top_k=3)
        labels = {item.experience.experience_id: True for item in candidates}
        selected_id = candidates[0].experience.experience_id
        labels[selected_id] = False
        record = measure_retrieval_funnel(
            query=query,
            candidates=candidates,
            applicability=labels,
            exposed_experience_ids=[selected_id],
        )
        self.assertTrue(record.candidate_inapplicability)
        self.assertTrue(record.selected_inapplicability)
        self.assertTrue(record.exposed_inapplicability)
        aggregate = aggregate_funnel([record])
        self.assertEqual(aggregate["selected_inapplicability_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
