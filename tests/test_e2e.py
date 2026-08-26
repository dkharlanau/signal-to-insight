from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from build import render_page  # noqa: E402
from build_previews import render_preview  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "e2e.json"
FORBIDDEN_RAW_KEYS = {
    "transcript",
    "full_transcript",
    "raw_text",
    "full_text",
    "article_body",
    "pdf_text",
    "source_content",
}


def find_forbidden_keys(node: object) -> list[str]:
    found: list[str] = []
    stack = [node]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            for key, value in current.items():
                if key.lower() in FORBIDDEN_RAW_KEYS:
                    found.append(key)
                stack.append(value)
        elif isinstance(current, list):
            stack.extend(current)
    return found


class PipelineAcceptanceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_identifier_chain_is_coherent(self) -> None:
        intake = self.data["intake"]
        bundle = self.data["bundle"]
        source = self.data["source"]
        insight = self.data["insight"]

        self.assertEqual(bundle["intake_id"], intake["id"])
        self.assertEqual(intake["source_id"], source["id"])
        self.assertEqual(bundle["source_id"], source["id"])
        self.assertEqual(insight["source_id"], source["id"])
        self.assertEqual(intake["insight_id"], insight["id"])
        self.assertIn(insight["id"], source["derived_records"])
        self.assertEqual(bundle["source"]["canonical_url"], intake["source_url"])
        self.assertEqual(source["canonical_url"], intake["source_url"])

    def test_public_bundle_does_not_contain_raw_source_dump(self) -> None:
        bundle = self.data["bundle"]
        self.assertFalse(bundle["inspection"]["full_content_committed"])
        self.assertEqual(find_forbidden_keys(bundle), [])

    def test_published_page_is_deterministic_and_public(self) -> None:
        insight = self.data["insight"]
        source = self.data["source"]

        first = render_page(insight, source)
        second = render_page(copy.deepcopy(insight), copy.deepcopy(source))

        self.assertEqual(first, second)
        self.assertIn('rel="canonical"', first)
        self.assertIn('application/ld+json', first)
        self.assertNotIn('noindex,nofollow', first)
        self.assertIn(source["canonical_url"], first)
        self.assertIn(source["published_at"], first)
        self.assertIn(insight["title"], first)

    def test_review_preview_is_visually_reviewable_but_not_public(self) -> None:
        insight = copy.deepcopy(self.data["insight"])
        insight["status"] = "review"
        source = self.data["source"]

        first = render_preview(insight, source)
        second = render_preview(copy.deepcopy(insight), copy.deepcopy(source))

        self.assertEqual(first, second)
        self.assertIn('noindex,nofollow', first)
        self.assertNotIn('rel="canonical"', first)
        self.assertNotIn('application/ld+json', first)
        self.assertIn('REVIEW PREVIEW · NOT INDEXED · NOT PUBLISHED', first)
        self.assertIn('preview-page', first)
        self.assertIn(insight["title"], first)

    def test_publication_boundary_uses_review_before_published(self) -> None:
        intake = self.data["intake"]
        insight = self.data["insight"]
        self.assertEqual(intake["status"], "review")
        self.assertEqual(insight["status"], "published")
        self.assertNotEqual(intake["status"], "published")


if __name__ == "__main__":
    unittest.main()
