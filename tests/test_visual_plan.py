from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from build import render_dominant_visual  # noqa: E402

FIXTURE = json.loads((ROOT / "tests" / "fixtures" / "e2e.json").read_text(encoding="utf-8"))["insight"]


class VisualPlanTest(unittest.TestCase):
    def insight_for(self, visual_type: str, node_count: int = 3) -> dict:
        insight = copy.deepcopy(FIXTURE)
        nodes = [
            {"label": f"0{i + 1}", "title": f"Node {i + 1}", "text": f"Text {i + 1}"}
            for i in range(node_count)
        ]
        insight["visual_plan"]["dominant"] = {
            "type": visual_type,
            "title": f"{visual_type} example",
            "nodes": nodes,
        }
        return insight

    def test_causal_chain_uses_model_flow(self) -> None:
        html = render_dominant_visual(self.insight_for("causal_chain"))
        self.assertIn('class="model-flow"', html)
        self.assertEqual(html.count("<article>"), 3)
        self.assertEqual(html.count("<b>→</b>"), 2)

    def test_sequence_uses_sequence_primitive(self) -> None:
        html = render_dominant_visual(self.insight_for("sequence", 4))
        self.assertIn('class="visual-sequence"', html)
        self.assertEqual(html.count("<article>"), 4)

    def test_layers_use_layers_primitive(self) -> None:
        html = render_dominant_visual(self.insight_for("layers", 3))
        self.assertIn('class="visual-layers"', html)

    def test_comparison_uses_comparison_primitive(self) -> None:
        html = render_dominant_visual(self.insight_for("comparison", 2))
        self.assertIn('class="visual-compare"', html)
        self.assertEqual(html.count("<article>"), 2)

    def test_decision_uses_decision_primitive(self) -> None:
        html = render_dominant_visual(self.insight_for("decision", 3))
        self.assertIn('class="visual-decision"', html)


if __name__ == "__main__":
    unittest.main()
