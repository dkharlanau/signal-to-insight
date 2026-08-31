from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from evidence_handoff import HandoffError, build_packet, serialize, validate_packet  # noqa: E402


class EvidenceHandoffTest(unittest.TestCase):
    def fixture(self, status: str = "published") -> tuple[dict, dict, dict]:
        insights = {
            "insights": [
                {
                    "id": "insight-1",
                    "source_id": "source-1",
                    "slug": "insight-one",
                    "status": status,
                    "title": "Insight one",
                    "one_liner": "A compact reviewed model.",
                    "tags": ["z", "a", "a"],
                    "provenance": {"reviewed_at": "2026-08-31"},
                }
            ]
        }
        sources = {
            "sources": [
                {
                    "id": "source-1",
                    "type": "article",
                    "title": "Source one",
                    "canonical_url": "https://example.com/source",
                    "creators": ["Example Author"],
                    "publisher": "Example",
                    "published_at": "2026-08-01",
                    "event_date": None,
                    "captured_at": "2026-08-31",
                    "analyzed_at": "2026-08-31",
                }
            ]
        }
        claims = {
            "records": [
                {
                    "insight_id": "insight-1",
                    "claims": [
                        {
                            "id": "claim-1",
                            "text": "A reviewed claim.",
                            "impact": "high",
                            "origin": "source",
                            "status": "supported",
                            "evidence": [
                                {
                                    "kind": "primary_source",
                                    "source_id": "source-1",
                                    "url": "https://example.com/source",
                                    "locator": "Section one",
                                }
                            ],
                            "note": None,
                        }
                    ],
                }
            ]
        }
        return insights, sources, claims

    def test_export_is_deterministic_and_valid(self) -> None:
        inputs = self.fixture()
        first = build_packet("insight-1", *inputs)
        second = build_packet("insight-1", *copy.deepcopy(inputs))
        self.assertEqual(first, second)
        self.assertEqual(validate_packet(first), [])
        self.assertEqual(first["exported_from"]["tags"], ["a", "z"])
        self.assertNotIn("transcript", serialize(first).lower())

    def test_review_only_insight_cannot_be_exported(self) -> None:
        with self.assertRaisesRegex(HandoffError, "only published insights"):
            build_packet("insight-1", *self.fixture(status="review"))

    def test_tampering_breaks_digest(self) -> None:
        packet = build_packet("insight-1", *self.fixture())
        packet["claims"][0]["text"] = "Tampered"
        self.assertIn(
            "integrity.digest does not match the canonical packet payload",
            validate_packet(packet),
        )

    def test_raw_source_content_is_rejected(self) -> None:
        packet = build_packet("insight-1", *self.fixture())
        packet["source"]["full_text"] = "must not cross the boundary"
        errors = validate_packet(packet)
        self.assertTrue(any("forbidden raw-source keys" in error for error in errors))

    def test_committed_reference_packet_is_current(self) -> None:
        packet = build_packet("enterprise-agents-production-substrate")
        expected = ROOT / "examples" / "research-evidence-handoff" / "enterprise-agents-production-substrate.json"
        self.assertTrue(expected.exists())
        self.assertEqual(expected.read_text(encoding="utf-8"), serialize(packet))


if __name__ == "__main__":
    unittest.main()
