from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from queue_issue import build_queue_result, parse_issue_body  # noqa: E402


BODY = """### Source URL

https://www.youtube.com/watch?v=abc123&t=120&utm_source=test

### Source type

video

### Focus

Understand the architecture and tools.

### Note

Interesting talk.
"""


class IssueIntakeTest(unittest.TestCase):
    def event(self) -> dict:
        return {
            "issue": {
                "number": 42,
                "created_at": "2026-08-26T10:00:00Z",
                "body": BODY,
            }
        }

    def test_issue_form_sections_parse(self) -> None:
        fields = parse_issue_body(BODY)
        self.assertEqual(fields["Source type"], "video")
        self.assertEqual(fields["Focus"], "Understand the architecture and tools.")
        self.assertEqual(fields["Note"], "Interesting talk.")

    def test_owner_workflow_record_uses_canonical_inbox_contract(self) -> None:
        inbox = {"queue_version": "1.0.0", "items": []}
        sources = {"sources": []}
        result = build_queue_result(self.event(), inbox, sources)

        self.assertTrue(result["changed"])
        self.assertEqual(result["status"], "queued")
        self.assertEqual(result["url"], "https://www.youtube.com/watch?v=abc123")
        self.assertEqual(len(inbox["items"]), 1)
        item = inbox["items"][0]
        self.assertEqual(item["source_type"], "video")
        self.assertEqual(item["submitted_at"], "2026-08-26")
        self.assertEqual(item["status"], "queued")
        self.assertIsNone(item["source_id"])
        self.assertIsNone(item["insight_id"])
        self.assertIn("GitHub source intake issue #42", item["notes"])

    def test_duplicate_focus_does_not_add_second_item(self) -> None:
        inbox = {"queue_version": "1.0.0", "items": []}
        sources = {"sources": []}
        first = build_queue_result(self.event(), inbox, sources)
        second = build_queue_result(self.event(), inbox, sources)

        self.assertTrue(first["changed"])
        self.assertFalse(second["changed"])
        self.assertEqual(second["status"], "already_queued")
        self.assertEqual(len(inbox["items"]), 1)

    def test_registered_source_wins_over_queue(self) -> None:
        inbox = {"queue_version": "1.0.0", "items": []}
        sources = {
            "sources": [
                {
                    "id": "src-known-2026",
                    "canonical_url": "https://www.youtube.com/watch?v=abc123",
                }
            ]
        }
        result = build_queue_result(self.event(), inbox, sources)
        self.assertFalse(result["changed"])
        self.assertEqual(result["status"], "known_source")
        self.assertEqual(result["id"], "src-known-2026")
        self.assertEqual(inbox["items"], [])

    def test_different_focus_can_create_second_request(self) -> None:
        inbox = {"queue_version": "1.0.0", "items": []}
        sources = {"sources": []}
        build_queue_result(self.event(), inbox, sources)

        changed_event = copy.deepcopy(self.event())
        changed_event["issue"]["body"] = BODY.replace(
            "Understand the architecture and tools.",
            "Focus only on evaluation patterns.",
        )
        result = build_queue_result(changed_event, inbox, sources)
        self.assertTrue(result["changed"])
        self.assertEqual(len(inbox["items"]), 2)


if __name__ == "__main__":
    unittest.main()
