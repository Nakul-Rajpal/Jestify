"""Curated few-shot examples for ManimCE code generation (LLM Call #2).

Five complete, runnable ManimCE scenes covering all major scene types.
Each example is formatted as the exact JSON the LLM must output.

Key patterns demonstrated:
  Ex 1 (concept_reveal) — title + equation + labeled VGroup, SurroundingRectangle
  Ex 2 (equation)       — step-by-step ReplacementTransform, FadeOut before new text
  Ex 3 (graph)          — Axes with Text() labels, axes.plot(), axes.c2p(), get_area()
  Ex 4 (diagram)        — multi-section with section cleanup, LaggedStart for lists
  Ex 5 (summary)        — VGroup card layout, LaggedStart reveal, Indicate emphasis
"""

# ── manim_examples.py exports ─────────────────────────────────────────────────
#
#   MANIM_CODE_FEWSHOT  — drop-in replacement for CODE_FEWSHOT in fewshot_examples.py
#

MANIM_CODE_FEWSHOT = r"""
=== FEW-SHOT EXAMPLES ===
Study every example carefully. Your output MUST follow the same patterns:
- Title at UP*3.2 for EVERY scene
- All text via Text() with Unicode math (NEVER MathTex/Tex)
- Explicit run_time on every self.play()
- FadeOut old text BEFORE writing new text in the same region
- Section cleanup: self.play(*[FadeOut(m) for m in self.mobjects if m is not title])
- KEEP final content VISIBLE — end with self.wait(2), NO FadeOut at end
- text.set_width(min(text.width, 8.5)) after every Text() creation

CRITICAL PATTERN — TEXT OVERLAP PREVENTION:
Every example below FadeOuts old text BEFORE adding new text in the same area.
Missing this causes the #1 visual quality failure: overlapping text on screen.

--- EXAMPLE 1: concept_reveal — title + formula + labeled breakdown ---
Narration: "Ohm's Law is the foundation of electrical circuits. The voltage
across a component equals the current flowing through it multiplied by its
resistance. Remember these three quantities — voltage, current, resistance —
and you can analyse any basic circuit."
Scene type: concept_reveal, Duration: 20s

Code output:
{
    "scene_index": 0,
    "manim_code": "from manim import *\nimport numpy as np\n\nclass Scene000(MovingCameraScene):\n    def construct(self):\n        # Title — always at UP * 3.2\n        title = Text(\"Ohm's Law: V = I \u00d7 R\", font_size=44, weight=BOLD, color=GOLD)\n        title.move_to(UP * 3.2)\n        self.play(Write(title), run_time=1.2)\n        self.wait(0.5)\n        # Central formula — large, centred in safe zone\n        formula = Text(\"V = I \u00d7 R\", font_size=56, color=WHITE)\n        formula.move_to(DOWN * 0.3)\n        formula.set_width(min(formula.width, 8.5))\n        self.play(Write(formula), run_time=1.5)\n        self.wait(0.8)\n        # Three color-coded labels — VGroup.arrange() prevents overlap\n        v_desc = Text(\"V = Voltage (Volts)\", font_size=28, color=YELLOW)\n        i_desc = Text(\"I = Current (Amperes)\", font_size=28, color=BLUE_B)\n        r_desc = Text(\"R = Resistance (\u03a9)\", font_size=28, color=RED_B)\n        labels = VGroup(v_desc, i_desc, r_desc)\n        labels.arrange(DOWN, buff=0.4)\n        labels.next_to(formula, DOWN, buff=0.7)\n        # LaggedStart for staggered reveal — never bulk FadeIn\n        self.play(\n            LaggedStart(*[FadeIn(l, shift=UP * 0.3) for l in labels], lag_ratio=0.3),\n            run_time=1.8,\n        )\n        self.wait(0.8)\n        # Highlight formula — box then Indicate\n        box = SurroundingRectangle(formula, color=GOLD, buff=0.2)\n        self.play(Create(box), run_time=1.0)\n        self.play(Indicate(formula, color=GOLD, scale_factor=1.1), run_time=1.2)\n        self.wait(2)"
}

--- EXAMPLE 2: equation — step-by-step derivation with ReplacementTransform ---
Narration: "Let's derive the quadratic formula step by step. We start with
the standard form ax squared plus bx plus c equals zero. By completing the
square and isolating x, we arrive at the famous formula: x equals negative b
plus or minus the square root of b squared minus four ac, all divided by 2a.
The expression under the square root — b squared minus four ac — is called the
discriminant and tells us how many real solutions exist."
Scene type: equation, Duration: 20s

Code output:
{
    "scene_index": 2,
    "manim_code": "from manim import *\nimport numpy as np\n\nclass Scene002(MovingCameraScene):\n    def construct(self):\n        title = Text(\"The Quadratic Formula\", font_size=44, weight=BOLD, color=GOLD)\n        title.move_to(UP * 3.2)\n        self.play(Write(title), run_time=1.0)\n        self.wait(0.4)\n        # Step 1: standard form\n        step1 = Text(\"ax\u00b2 + bx + c = 0\", font_size=44, color=WHITE)\n        step1.move_to(DOWN * 0.3)\n        step1.set_width(min(step1.width, 8.5))\n        hint1 = Text(\"standard form\", font_size=26, color=GREY_B)\n        hint1.next_to(step1, DOWN, buff=0.5)\n        self.play(Write(step1), run_time=1.5)\n        self.play(FadeIn(hint1, shift=UP * 0.2), run_time=0.8)\n        self.wait(0.8)\n        # FadeOut helper text BEFORE next element (overlap prevention)\n        self.play(FadeOut(hint1), run_time=0.5)\n        # Step 2: solution — ReplacementTransform swaps in-place, no overlap\n        step2 = Text(\"x = (-b \u00b1 \u221a(b\u00b2-4ac)) / 2a\", font_size=36, color=GREEN_B)\n        step2.move_to(DOWN * 0.3)\n        step2.set_width(min(step2.width, 8.5))\n        self.play(ReplacementTransform(step1, step2), run_time=1.8)\n        self.wait(0.8)\n        # Discriminant label — next_to ensures it doesn't land on step2\n        disc = Text(\"b\u00b2 - 4ac = discriminant\", font_size=28, color=YELLOW)\n        disc.next_to(step2, DOWN, buff=0.6)\n        disc.set_width(min(disc.width, 8.5))\n        self.play(FadeIn(disc, shift=UP * 0.2), run_time=1.0)\n        self.wait(0.6)\n        # Box + Indicate to emphasise the result\n        box = SurroundingRectangle(step2, color=GREEN, buff=0.2)\n        self.play(Create(box), run_time=1.0)\n        self.play(Indicate(step2, color=GREEN, scale_factor=1.05), run_time=1.2)\n        self.wait(2)"
}

--- EXAMPLE 3: graph — Axes + plot + annotations (Text labels, c2p, get_area) ---
Narration: "Here is the function f of x equals x squared — a classic parabola.
Notice how the curve starts flat near the origin and then rises steeply on both
sides. The minimum value is zero, right at x equals zero. The shaded region
shows the area under the curve between negative two and positive two."
Scene type: graph, Duration: 22s

Code output:
{
    "scene_index": 1,
    "manim_code": "from manim import *\nimport numpy as np\n\nclass Scene001(MovingCameraScene):\n    def construct(self):\n        title = Text(\"Visualising f(x) = x\u00b2\", font_size=44, weight=BOLD, color=GOLD)\n        title.move_to(UP * 3.2)\n        self.play(Write(title), run_time=1.0)\n        # Axes — small ranges only; Text() labels to avoid hidden LaTeX\n        axes = Axes(\n            x_range=[-3, 3, 1], y_range=[-1, 9, 2],\n            x_length=7, y_length=5,\n            axis_config={\"include_numbers\": True},\n        )\n        axes.move_to(DOWN * 0.3)\n        x_lab = axes.get_x_axis_label(Text(\"x\", font_size=28))\n        y_lab = axes.get_y_axis_label(Text(\"f(x)\", font_size=28))\n        self.play(Create(axes), Write(x_lab), Write(y_lab), run_time=1.8)\n        self.wait(0.5)\n        # Plot using axes.plot() — NOT get_graph()\n        graph = axes.plot(lambda x: x ** 2, color=BLUE, x_range=[-2.8, 2.8])\n        graph_label = Text(\"f(x) = x\u00b2\", color=BLUE, font_size=28)\n        graph_label.next_to(axes.c2p(2.2, 4.84), RIGHT, buff=0.3)\n        self.play(Create(graph), FadeIn(graph_label, shift=UP * 0.3), run_time=2.0)\n        self.wait(0.5)\n        # Annotate minimum — dot + label positioned with next_to (no overlap)\n        min_dot = Dot(axes.c2p(0, 0), color=GREEN, radius=0.12)\n        min_label = Text(\"min at (0, 0)\", font_size=24, color=GREEN)\n        min_label.next_to(min_dot, UL, buff=0.4)\n        min_label.set_width(min(min_label.width, 3.5))\n        self.play(FadeIn(min_dot), FadeIn(min_label, shift=UP * 0.2), run_time=1.0)\n        self.wait(0.5)\n        # Shaded area — FadeOut min_label first to free up the space\n        area = axes.get_area(graph, x_range=[-2, 2], color=BLUE, opacity=0.2)\n        self.play(FadeOut(min_label), run_time=0.4)\n        area_lbl = Text(\"area from -2 to 2\", font_size=24, color=BLUE_B)\n        area_lbl.next_to(axes.c2p(0, 4), LEFT, buff=0.3)\n        area_lbl.set_width(min(area_lbl.width, 3.5))\n        self.play(FadeIn(area), FadeIn(area_lbl), run_time=1.5)\n        self.wait(0.8)\n        self.play(Indicate(graph, color=YELLOW, scale_factor=1.02), run_time=1.5)\n        self.wait(2)"
}

--- EXAMPLE 4: diagram — multi-section with section cleanup between topics ---
Narration: "Merge sort is a divide-and-conquer sorting algorithm. In the first
step we divide the unsorted array into two halves. In the second step, each
half is recursively sorted. Finally, the two sorted halves are merged back
together, producing a fully sorted array. The time complexity is O of n log n."
Scene type: diagram, Duration: 25s

Code output:
{
    "scene_index": 3,
    "manim_code": "from manim import *\nimport numpy as np\n\nclass Scene003(MovingCameraScene):\n    def construct(self):\n        title = Text(\"Merge Sort: Divide and Conquer\", font_size=40, weight=BOLD, color=GOLD)\n        title.move_to(UP * 3.2)\n        self.play(Write(title), run_time=1.0)\n        self.wait(0.4)\n        # === SECTION 1: DIVIDE ===\n        s1 = Text(\"Step 1: Divide the array\", font_size=30, color=BLUE_B, weight=BOLD)\n        s1.move_to(UP * 1.8)\n        values = [5, 2, 8, 1, 9, 3, 7, 4]\n        boxes = VGroup()\n        for v in values:\n            r = RoundedRectangle(corner_radius=0.1, width=0.8, height=0.8, color=BLUE)\n            t = Text(str(v), font_size=22)\n            t.move_to(r.get_center())\n            boxes.add(VGroup(r, t))\n        boxes.arrange(RIGHT, buff=0.1)\n        boxes.set_width(min(boxes.width, 8.5))\n        boxes.move_to(DOWN * 0.3)\n        self.play(FadeIn(s1, shift=DOWN * 0.2), run_time=0.8)\n        self.play(\n            LaggedStart(*[FadeIn(b, shift=UP * 0.2) for b in boxes], lag_ratio=0.08),\n            run_time=1.2,\n        )\n        split = DashedLine(DOWN * 0.05, DOWN * 0.85, color=YELLOW)\n        split.move_to(boxes.get_center())\n        self.play(Create(split), run_time=0.8)\n        self.wait(0.5)\n        # Section cleanup — keep ONLY title (mandatory between sections)\n        self.play(*[FadeOut(m) for m in self.mobjects if m is not title], run_time=0.8)\n        # === SECTION 2: SORTED HALVES ===\n        s2 = Text(\"Step 2: Sort each half\", font_size=30, color=GREEN_B, weight=BOLD)\n        s2.move_to(UP * 1.8)\n        left_vals = [1, 2, 5, 8]\n        right_vals = [3, 4, 7, 9]\n        def make_row(vals, color):\n            g = VGroup()\n            for v in vals:\n                r = RoundedRectangle(corner_radius=0.1, width=0.8, height=0.8, color=color)\n                t = Text(str(v), font_size=22)\n                t.move_to(r.get_center())\n                g.add(VGroup(r, t))\n            g.arrange(RIGHT, buff=0.1)\n            return g\n        left_row = make_row(left_vals, GREEN)\n        right_row = make_row(right_vals, TEAL)\n        left_row.move_to(LEFT * 2.5 + DOWN * 0.3)\n        right_row.move_to(RIGHT * 2.5 + DOWN * 0.3)\n        self.play(FadeIn(s2, shift=DOWN * 0.2), run_time=0.8)\n        self.play(FadeIn(left_row, shift=RIGHT * 0.2), FadeIn(right_row, shift=LEFT * 0.2), run_time=1.2)\n        self.wait(0.5)\n        self.play(*[FadeOut(m) for m in self.mobjects if m is not title], run_time=0.8)\n        # === SECTION 3: MERGED RESULT ===\n        s3 = Text(\"Result: Fully Sorted!\", font_size=30, color=YELLOW, weight=BOLD)\n        s3.move_to(UP * 1.8)\n        sorted_vals = [1, 2, 3, 4, 5, 7, 8, 9]\n        result_row = make_row(sorted_vals, GOLD)\n        result_row.set_width(min(result_row.width, 8.5))\n        result_row.move_to(DOWN * 0.3)\n        self.play(FadeIn(s3, shift=DOWN * 0.2), run_time=0.8)\n        self.play(\n            LaggedStart(*[FadeIn(b, shift=UP * 0.3) for b in result_row], lag_ratio=0.08),\n            run_time=1.5,\n        )\n        self.wait(0.6)\n        complexity = Text(\"Time Complexity: O(n log n)\", font_size=28, color=YELLOW)\n        complexity.next_to(result_row, DOWN, buff=0.6)\n        complexity.set_width(min(complexity.width, 8.5))\n        self.play(Write(complexity), run_time=1.2)\n        self.play(Circumscribe(complexity, color=YELLOW), run_time=1.2)\n        self.wait(2)"
}

--- EXAMPLE 5: summary — VGroup card layout, LaggedStart, Indicate, dim/restore ---
Narration: "Let's review the four key differentiation rules you must know.
The power rule tells us how to differentiate monomials. The product rule
handles the derivative of a product of two functions. The chain rule covers
composite functions. And the fundamental theorem of calculus links
differentiation and integration. Master these four rules and you can
differentiate almost any function."
Scene type: summary, Duration: 20s

Code output:
{
    "scene_index": 4,
    "manim_code": "from manim import *\nimport numpy as np\n\nclass Scene004(MovingCameraScene):\n    def construct(self):\n        title = Text(\"Key Differentiation Rules\", font_size=44, weight=BOLD, color=GOLD)\n        title.move_to(UP * 3.2)\n        self.play(Write(title), run_time=1.0)\n        self.wait(0.4)\n        # Card data — (rule name, formula, accent colour)\n        rules_data = [\n            (\"Power Rule\", \"xⁿ  →  nxⁿ⁻¹\", BLUE),\n            (\"Product Rule\", \"(fg)' = f'g + fg'\", GREEN),\n            (\"Chain Rule\", \"d/dx[f(g(x))] = f'(g(x)) · g'(x)\", YELLOW),\n            (\"Fund. Theorem\", \"∫ₐᵇ f(x)dx = F(b) - F(a)\", RED_B),\n        ]\n        cards = VGroup()\n        for rule_name, formula_str, color in rules_data:\n            rect = RoundedRectangle(\n                corner_radius=0.2, width=10.5, height=0.85,\n                color=color, fill_opacity=0.08, stroke_width=2,\n            )\n            name_lbl = Text(rule_name + \":\", font_size=26, color=color, weight=BOLD)\n            form_lbl = Text(formula_str, font_size=24, color=WHITE)\n            form_lbl.set_width(min(form_lbl.width, 7.0))\n            row = VGroup(name_lbl, form_lbl)\n            row.arrange(RIGHT, buff=0.5)\n            row.set_width(min(row.width, 9.5))\n            row.move_to(rect.get_center())\n            cards.add(VGroup(rect, row))\n        cards.arrange(DOWN, buff=0.35)\n        cards.move_to(DOWN * 0.3)\n        # LaggedStart — mandatory for list reveals, never bulk FadeIn\n        self.play(\n            LaggedStart(*[FadeIn(c, shift=UP * 0.3) for c in cards], lag_ratio=0.25),\n            run_time=2.5,\n        )\n        self.wait(0.8)\n        # Highlight power rule (most fundamental)\n        self.play(Indicate(cards[0], color=BLUE, scale_factor=1.04), run_time=1.2)\n        self.wait(0.5)\n        # Dim first two, highlight chain rule\n        self.play(\n            cards[0].animate.set_opacity(0.4),\n            cards[1].animate.set_opacity(0.4),\n            run_time=0.6,\n        )\n        self.play(Indicate(cards[2], color=YELLOW, scale_factor=1.04), run_time=1.2)\n        self.wait(0.5)\n        # Restore all cards\n        self.play(*[c.animate.set_opacity(1.0) for c in cards], run_time=0.6)\n        self.wait(0.6)\n        # Clear cards then show outro — FadeOut before new content (overlap prevention)\n        self.play(*[FadeOut(c) for c in cards], run_time=0.8)\n        outro = Text(\"Master these rules to unlock calculus!\", font_size=32, color=GREEN_B)\n        outro.move_to(DOWN * 0.3)\n        outro.set_width(min(outro.width, 9.5))\n        self.play(Write(outro), run_time=1.2)\n        self.wait(2)"
}
"""
