from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class VisualExtensionSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = json.loads((ROOT / "data" / "visual-extensions.json").read_text(encoding="utf-8"))
        cls.runtime = (ROOT / "visual-extensions.js").read_text(encoding="utf-8")
        cls.bootstrap = (ROOT / "decision.js").read_text(encoding="utf-8")
        cls.styles = (ROOT / "visual-extensions.css").read_text(encoding="utf-8")

    def record(self, primitive: str) -> dict:
        return next(item for item in self.payload["records"] if item["primitive"] == primitive)

    def test_real_corpus_exercises_all_new_primitives(self):
        self.assertEqual(
            {"decision_tree", "state_transition", "source_figure"},
            {item["primitive"] for item in self.payload["records"]},
        )
        self.assertEqual(
            {
                "open-policy-agent-decision-enforcement-model",
                "temporal-durable-execution-mental-model",
                "react-reason-act-observe-loop",
            },
            {item["insight_id"] for item in self.payload["records"]},
        )

    def test_runtime_has_distinct_renderers_and_keeps_base_on_failure(self):
        for marker in ("renderDecisionTree", "renderStateTransition", "renderSourceFigure", "fallbackBlock"):
            self.assertIn(marker, self.runtime)
        self.assertIn("The base generated visual remains intact", self.runtime)
        self.assertIn("image.addEventListener('error'", self.runtime)

    def test_page_shell_bootstraps_extension_assets(self):
        self.assertIn("../../visual-extensions.css", self.bootstrap)
        self.assertIn("../../visual-extensions.js", self.bootstrap)
        self.assertIn("dataset.visualExtensions", self.bootstrap)

    def test_source_figure_remains_remote_and_has_text_fallback(self):
        record = self.record("source_figure")
        figure = record["source_figure"]
        self.assertEqual("remote_source_owned", figure["copy_policy"])
        self.assertTrue(figure["url"].startswith("https://react-lm.github.io/"))
        self.assertGreaterEqual(len(record["fallback"]["items"]), 2)
        # The author figure is intentionally not mirrored into the repository.
        self.assertFalse((ROOT / "files" / "diagram.png").exists())
        self.assertFalse((ROOT / "assets" / "diagram.png").exists())

    def test_responsive_fallback_styles_exist(self):
        self.assertIn("@media (max-width: 640px)", self.styles)
        self.assertIn(".visual-extension-fallback", self.styles)
        self.assertIn(".source-figure-link img", self.styles)
        self.assertIn("grid-template-columns: 1fr", self.styles)


if __name__ == "__main__":
    unittest.main()
