from __future__ import annotations

import unittest

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import scaffold_bundle  # noqa: E402
import validate_bundles  # noqa: E402


class PriorKnowledgeTests(unittest.TestCase):
    def setUp(self) -> None:
        validate_bundles.errors.clear()

    def tearDown(self) -> None:
        validate_bundles.errors.clear()

    def fixture_bundle(self, classification: str = "unclassified") -> dict:
        return {
            "source_id": "src-test",
            "source": {"canonical_url": "https://example.com/source"},
            "prior_knowledge": {
                "captured_at": "2026-08-26",
                "query": "durable workflow",
                "classification_required": True,
                "matches": [
                    {
                        "concept_id": "durable-execution",
                        "label": "Durable execution",
                        "coverage": "explained",
                        "evidence_insights": [
                            {"id": "existing-insight", "status": "published", "title": "Existing insight"}
                        ],
                        "relationship_to_source": classification,
                    }
                ],
            },
        }

    def validate(self, bundle: dict, statuses: set[str]) -> list[str]:
        validate_bundles.validate_prior_knowledge(
            bundle=bundle,
            rel=Path("data/research-bundles/test.json"),
            graph_ids={"durable-execution"},
            insight_ids={"existing-insight"},
            insight_status_by_source={"src-test": statuses},
            source_id_by_url={"https://example.com/source": "src-test"},
        )
        return list(validate_bundles.errors)

    def test_review_is_blocked_when_prior_knowledge_is_unclassified(self) -> None:
        errors = self.validate(self.fixture_bundle("unclassified"), {"review"})
        self.assertTrue(any("block insight state" in error for error in errors), errors)

    def test_draft_can_keep_prior_knowledge_unclassified(self) -> None:
        errors = self.validate(self.fixture_bundle("unclassified"), {"draft"})
        self.assertFalse(any("block insight state" in error for error in errors), errors)

    def test_review_is_allowed_after_classification(self) -> None:
        errors = self.validate(self.fixture_bundle("refinement"), {"review"})
        self.assertEqual([], errors)

    def test_new_bundle_scaffold_captures_prior_knowledge(self) -> None:
        item = {
            "id": "intake-self-test",
            "source_id": None,
            "source_type": "article",
            "source_url": "https://example.com/durable-workflow-retry",
            "requested_focus": "durable workflow retry",
        }
        bundle = scaffold_bundle.build_bundle(item, "2026-08-26")
        prior = bundle["prior_knowledge"]
        ids = {match["concept_id"] for match in prior["matches"]}
        self.assertIn("durable-execution", ids)
        self.assertTrue(prior["classification_required"])
        self.assertTrue(all(match["relationship_to_source"] == "unclassified" for match in prior["matches"]))


if __name__ == "__main__":
    unittest.main()
