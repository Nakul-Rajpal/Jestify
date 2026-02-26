"""Curated few-shot examples for narration and code generation prompts.

These examples are embedded in system prompts to guide Claude toward
higher-quality, more consistent outputs — the closest available
alternative to fine-tuning for Sonnet 4.
"""

# ──────────────────────────────────────────────────────────────────────
# NARRATION FEW-SHOT EXAMPLES
# ──────────────────────────────────────────────────────────────────────

NARRATION_FEWSHOT = r"""
=== FEW-SHOT EXAMPLES ===
Study these examples carefully. Your output MUST follow the same JSON
structure, narration style, and visual description specificity.

--- EXAMPLE 1 (beginner, graph scene) ---
Source material: "Introduction to derivatives. The derivative of a function
measures the rate of change at any point. For f(x) = x², the derivative
f'(x) = 2x tells us the slope of the tangent line at every point."
Character: LeBron James

Output:
{
    "title": "Derivatives: Reading the Defense",
    "total_scenes": 5,
    "scenes": [
        {
            "scene_index": 0,
            "narration_text": "Let's lock in, team. Think about reading a defense in basketball — you gotta see what's changing in real time. That's exactly what a derivative does. It tells you the rate of change at any point, like knowing which direction the play is shifting before anyone else does. Stay focused, because we're about to break this down.",
            "visual_description": "Title 'Derivatives: Reading the Defense' appears with a Write animation, then shifts to top. A basketball icon fades in briefly, then fades out to transition to math content.",
            "manim_scene_type": "concept_reveal",
            "duration_hint_seconds": 22,
            "character_action": "talking"
        },
        {
            "scene_index": 1,
            "narration_text": "Here's our function f(x) equals x squared. Watch this curve — it starts slow near zero, then accelerates as x grows. Now see that tangent line? That's the derivative in action, showing the slope right at that exact point. Great fundamentals right here.",
            "visual_description": "Show axes with f(x) = x² plotted as a blue curve. A yellow tangent line appears at x=1 and slides along the curve to x=2, showing how the slope changes. Label the function and the tangent line.",
            "manim_scene_type": "graph",
            "duration_hint_seconds": 22,
            "character_action": "talking"
        },
        {
            "scene_index": 2,
            "narration_text": "Now let's see the math behind it. We start with f(x) equals x squared. Apply the power rule — bring down the exponent, reduce by one — and we get f prime of x equals 2x. Watch how one expression transforms into the other. That's the play.",
            "visual_description": "Display 'f(x) = x²' centered. Then use ReplacementTransform to morph it into 'f'(x) = 2x'. Show an arrow labeled 'Power Rule' between them. Highlight the result in green.",
            "manim_scene_type": "equation",
            "duration_hint_seconds": 20,
            "character_action": "talking"
        },
        {
            "scene_index": 3,
            "narration_text": "Let's plug in some values. At x equals 1, the derivative is 2 — a gentle slope. At x equals 2, it's 4 — steeper. At x equals 3, it's 6 — even steeper. The function accelerates, and the derivative tracks that acceleration perfectly.",
            "visual_description": "Build a table or vertical stack showing x=1→f'=2, x=2→f'=4, x=3→f'=6. Use LaggedStart to reveal each row. Highlight each value with a color scale from green (gentle) to red (steep).",
            "manim_scene_type": "diagram",
            "duration_hint_seconds": 20,
            "character_action": "talking"
        },
        {
            "scene_index": 4,
            "narration_text": "So remember — the derivative is your ability to read the game in real time. It tells you exactly how fast things are changing at any moment. Master this fundamental, and everything in calculus builds from here. Let's keep pushing forward.",
            "visual_description": "Summary screen with title 'Key Takeaways'. Three bullet points fade in with LaggedStart: 'Derivative = rate of change', 'Power rule: xⁿ → nxⁿ⁻¹', 'Slope of tangent line at any point'. Fade out all at end.",
            "manim_scene_type": "summary",
            "duration_hint_seconds": 20,
            "character_action": "talking"
        }
    ],
    "intro_text": "Let's lock in and learn about derivatives.",
    "outro_text": "Keep pushing forward — calculus is your game now."
}

--- EXAMPLE 2 (intermediate, Peter Griffin) ---
Source material: "Binary search is an efficient algorithm for finding an item
in a sorted list. It works by repeatedly dividing the search interval in half."
Character: Peter Griffin

Output:
{
    "title": "Binary Search: Finding Stuff the Smart Way",
    "total_scenes": 5,
    "scenes": [
        {
            "scene_index": 0,
            "narration_text": "Hehehe, alright check this out. You know when you lose the TV remote and you're flipping couch cushions one by one? That's the dumb way. Binary search is the smart way — you cut the search area in half every single time. No way you'd find it faster than that.",
            "visual_description": "Title 'Binary Search' with Write animation, shifts to top. Show a row of numbered boxes 1-16 representing a sorted array. Highlight all of them briefly, then fade the highlight.",
            "manim_scene_type": "concept_reveal",
            "duration_hint_seconds": 22,
            "character_action": "talking"
        },
        {
            "scene_index": 1,
            "narration_text": "So here's how it works. We got 16 numbers sorted in a row. We want to find number 11. Step one — check the middle. Is 8 our target? Nope, 11 is bigger. So we throw away the entire left half. Boom, half the work gone in one shot.",
            "visual_description": "Show 16 boxes in a row. Highlight the middle element (8). Compare with target 11. Dim the left half (1-8) with set_opacity(0.3). Highlight the remaining right half (9-16).",
            "manim_scene_type": "diagram",
            "duration_hint_seconds": 22,
            "character_action": "talking"
        },
        {
            "scene_index": 2,
            "narration_text": "Now let's see why this is so fast. With linear search, you might check all 16 elements. But with binary search, you only need log base 2 of n steps. For 16 elements, that's just 4 checks. Watch this graph — linear grows like a straight line, but binary barely moves.",
            "visual_description": "Show axes with two plotted functions: linear search O(n) in red growing steeply, and binary search O(log n) in green staying low. Label both curves. Add a vertical dashed line at n=16 showing the comparison.",
            "manim_scene_type": "graph",
            "duration_hint_seconds": 22,
            "character_action": "talking"
        },
        {
            "scene_index": 3,
            "narration_text": "Here's the key idea in equation form. We start with n elements, then n over 2, then n over 4. Each step divides by 2 until we find our target or run out of elements. The number of steps is log base 2 of n. That's the power of divide and conquer.",
            "visual_description": "Show 'n → n/2 → n/4 → n/8 → ... → 1' with ReplacementTransform stepping through each reduction. Then transform the whole sequence into 'Steps = log₂(n)'. Highlight the final result in green.",
            "manim_scene_type": "equation",
            "duration_hint_seconds": 20,
            "character_action": "talking"
        },
        {
            "scene_index": 4,
            "narration_text": "So there you go. Binary search cuts your problem in half every step. It only works on sorted data, but when it works, it's insanely fast. Hehehe, even I can find the remote now. Remember: sorted list plus divide and conquer equals efficiency.",
            "visual_description": "Summary screen with three bullet points appearing via LaggedStart: 'Only works on sorted data', 'Divides search space in half each step', 'Time complexity: O(log n)'. Fade out everything at the end.",
            "manim_scene_type": "summary",
            "duration_hint_seconds": 20,
            "character_action": "talking"
        }
    ],
    "intro_text": "Alright, check this out — binary search explained.",
    "outro_text": "Hehehe, even I can find stuff now."
}

--- EXAMPLE 3 (intermediate, Goku, non-math: DNA replication) ---
Source material: "DNA replication is the process by which a cell copies its DNA
before cell division. The double helix unwinds, each strand serves as a template,
and DNA polymerase builds the complementary strand. The result is two identical
DNA molecules."
Character: Goku

Output:
{
    "title": "DNA Replication: Power Up Your Cells",
    "total_scenes": 5,
    "scenes": [
        {
            "scene_index": 0,
            "narration_text": "Let's get stronger — and I mean at the cellular level! When I train to power up, my body needs to replicate every single cell. That process starts with DNA replication — copying the entire instruction manual of life. It's like making a perfect clone of your power level data before you split into two warriors. Let's break this down!",
            "visual_description": "Title 'DNA Replication: Power Up Your Cells' appears with Write animation, shifts to top. Show a simplified double helix shape with two intertwined curves in blue and green. Brief glow effect to grab attention.",
            "manim_scene_type": "concept_reveal",
            "duration_hint_seconds": 24,
            "character_action": "talking"
        },
        {
            "scene_index": 1,
            "narration_text": "First, the double helix has to unwind. An enzyme called helicase literally unzips the two strands apart, like pulling two power cables apart. See how the base pairs — those rungs on the ladder — break apart as the helix opens. Each strand becomes a template. That was awesome to figure out!",
            "visual_description": "Show a ladder-style DNA double helix. Animate it unwinding from the top — the two strands separating with a zipper-like motion. Label 'Helicase' with an arrow pointing to the separation point. Show the two separated strands spreading apart.",
            "manim_scene_type": "diagram",
            "duration_hint_seconds": 24,
            "character_action": "talking"
        },
        {
            "scene_index": 2,
            "narration_text": "Now DNA polymerase runs along each template strand and builds the complementary copy. Adenine always pairs with Thymine — A with T. Guanine always pairs with Cytosine — G with C. These rules never break. Watch the new strand growing one base pair at a time. Time to train that complementary pairing!",
            "visual_description": "Show one template strand on the left side. Animate base pairs appearing one by one on the right side: A pairs with T (yellow), G pairs with C (green). Label the pairs. Show DNA polymerase as an arrow moving down the strand, triggering each new pair with FadeIn animation.",
            "manim_scene_type": "diagram",
            "duration_hint_seconds": 26,
            "character_action": "talking"
        },
        {
            "scene_index": 3,
            "narration_text": "Here's the amazing part — both strands get copied simultaneously! The replication fork moves in both directions from the origin. One strand is copied continuously — that's the leading strand. The other is copied in fragments called Okazaki fragments. The efficiency is incredible. Let's get stronger just by understanding this!",
            "visual_description": "Show a graph with x-axis as time and y-axis showing 'DNA copied (%)'. Plot two lines: leading strand grows smoothly from 0 to 100%, lagging strand grows in steps representing Okazaki fragments. Label both lines and the Okazaki fragment steps.",
            "manim_scene_type": "graph",
            "duration_hint_seconds": 26,
            "character_action": "talking"
        },
        {
            "scene_index": 4,
            "narration_text": "So now you have two identical DNA molecules — each with one original strand and one new strand. That's called semi-conservative replication. Every time a cell divides, this whole process happens perfectly. The accuracy is unbelievable — one error per billion base pairs. That's the kind of precision we train for!",
            "visual_description": "Summary screen with title 'Key Takeaways'. Three bullet points reveal with LaggedStart: 'Helicase unwinds the double helix', 'Complementary base pairing: A-T, G-C', 'Semi-conservative: 1 old + 1 new strand'. Fade all out, then show 'Error rate: 1 in 10⁹ base pairs' in GOLD as the final memorable stat.",
            "manim_scene_type": "summary",
            "duration_hint_seconds": 24,
            "character_action": "talking"
        }
    ],
    "intro_text": "Let's get stronger — starting with the cellular level!",
    "outro_text": "That's the kind of precision we train for. Keep pushing!"
}
"""

# ──────────────────────────────────────────────────────────────────────
# CODE GENERATION FEW-SHOT EXAMPLES
# ──────────────────────────────────────────────────────────────────────

CODE_FEWSHOT = r"""
=== FEW-SHOT EXAMPLES ===
Study these examples carefully. Your code MUST follow the same patterns:
correct class naming, Text() for all text (no LaTeX), run_time on every
self.play(), final content kept visible (NO FadeOut at end), and proper grid positioning.

CRITICAL PATTERN — OVERLAP PREVENTION:
- Notice how EVERY example FadeOuts old text BEFORE adding new text in the same area.
- Use ReplacementTransform to swap text in-place (no overlap).
- Between sections, clear everything except title:
    self.play(*[FadeOut(m) for m in self.mobjects if m is not title], run_time=0.8)

--- EXAMPLE 1: Graph scene (Axes + plot) ---
Narration: "Here's our function f(x) equals x squared. Watch this curve —
it starts slow near zero, then accelerates as x grows. Now see that tangent
line? That's the derivative in action, showing the slope right at that point."
Scene type: graph, Duration: 22s

Code:
{
    "scenes": [
        {
            "scene_index": 1,
            "manim_code": "from manim import *\nimport numpy as np\n\nclass Scene001(MovingCameraScene):\n    def construct(self):\n        # Title\n        title = Text(\"The Derivative in Action\", font_size=44, weight=BOLD, color=GOLD)\n        title.move_to(UP * 3.2)\n        self.play(Write(title), run_time=1.2)\n\n        # Axes\n        axes = Axes(\n            x_range=[-3, 3, 1], y_range=[-1, 9, 2],\n            x_length=7, y_length=5,\n            axis_config={\"include_numbers\": True},\n        ).move_to(DOWN * 0.3)\n        x_lab = axes.get_x_axis_label(Text(\"x\", font_size=28))\n        y_lab = axes.get_y_axis_label(Text(\"f(x)\", font_size=28))\n        self.play(Create(axes), Write(x_lab), Write(y_lab), run_time=1.5)\n\n        # Plot f(x) = x²\n        graph = axes.plot(lambda x: x**2, color=BLUE, x_range=[-2.8, 2.8])\n        graph_label = Text(\"f(x) = x²\", color=BLUE, font_size=28)\n        graph_label.next_to(axes.c2p(2, 4), RIGHT)\n        self.play(Create(graph), FadeIn(graph_label, shift=UP * 0.3), run_time=1.5)\n        self.wait(0.6)\n\n        # Tangent line at x=1 — label positioned next to dot, not floating\n        x_val = 1\n        slope = 2 * x_val\n        tangent = axes.plot(\n            lambda x: slope * (x - x_val) + x_val**2,\n            color=YELLOW, x_range=[x_val - 1.5, x_val + 1.5],\n        )\n        dot = Dot(axes.c2p(x_val, x_val**2), color=YELLOW)\n        slope_label = Text(f\"slope = {slope}\", font_size=28, color=YELLOW)\n        slope_label.next_to(axes.c2p(x_val, x_val**2), UR, buff=0.4)\n        self.play(Create(tangent), Create(dot), FadeIn(slope_label), run_time=1.5)\n        self.wait(0.6)\n\n        # Move tangent to x=2 — use ReplacementTransform to SWAP labels (no overlap)\n        x_val2 = 2\n        slope2 = 2 * x_val2\n        tangent2 = axes.plot(\n            lambda x: slope2 * (x - x_val2) + x_val2**2,\n            color=YELLOW, x_range=[x_val2 - 1.2, x_val2 + 1.2],\n        )\n        dot2 = Dot(axes.c2p(x_val2, x_val2**2), color=YELLOW)\n        slope_label2 = Text(f\"slope = {slope2}\", font_size=28, color=YELLOW)\n        slope_label2.next_to(axes.c2p(x_val2, x_val2**2), UR, buff=0.4)\n        self.play(\n            ReplacementTransform(tangent, tangent2),\n            ReplacementTransform(dot, dot2),\n            ReplacementTransform(slope_label, slope_label2),\n            run_time=1.5,\n        )\n        self.wait(0.8)\n\n        # Hold final content visible for compositor\n        self.wait(2)"
        }
    ]
}

--- EXAMPLE 2: Equation/transform scene — shows section cleanup pattern ---
Narration: "We start with f(x) equals x squared. Apply the power rule —
bring down the exponent, reduce by one — and we get f prime of x equals 2x.
Watch how one expression transforms into the other."
Scene type: equation, Duration: 20s

Code:
{
    "scenes": [
        {
            "scene_index": 2,
            "manim_code": "from manim import *\nimport numpy as np\n\nclass Scene002(MovingCameraScene):\n    def construct(self):\n        # Title\n        title = Text(\"The Power Rule\", font_size=44, weight=BOLD, color=GOLD)\n        title.move_to(UP * 3.2)\n        self.play(Write(title), run_time=1.0)\n\n        # Section 1: Show the original function\n        func = Text(\"f(x) = x²\", font_size=40, color=WHITE)\n        func.move_to(DOWN * 0.3)\n        func.set_width(min(func.width, 8.5))\n        self.play(Write(func), run_time=1.2)\n        self.wait(0.6)\n\n        # Power rule label — positioned BELOW func, no overlap\n        arrow = Arrow(UP * 0.3, DOWN * 0.3, color=YELLOW).next_to(func, DOWN, buff=0.5)\n        rule_label = Text(\"Power Rule: bring down n, reduce by 1\", font_size=28, color=YELLOW)\n        rule_label.next_to(arrow, RIGHT, buff=0.3)\n        self.play(GrowArrow(arrow), FadeIn(rule_label, shift=RIGHT * 0.3), run_time=1.2)\n        self.wait(0.5)\n\n        # FadeOut helper content BEFORE transforming (prevents overlap)\n        self.play(FadeOut(arrow), FadeOut(rule_label), run_time=0.8)\n\n        # Section 2: Transform to derivative — ReplacementTransform swaps in-place\n        deriv = Text(\"f'(x) = 2x\", font_size=40, color=GREEN_B)\n        deriv.move_to(func.get_center())\n        deriv.set_width(min(deriv.width, 8.5))\n        self.play(ReplacementTransform(func, deriv), run_time=1.5)\n        self.wait(0.5)\n\n        # Highlight result — positioned relative to deriv, not floating\n        box = SurroundingRectangle(deriv, color=GREEN, buff=0.15)\n        result_text = Text(\"The derivative!\", font_size=32, color=GREEN)\n        result_text.next_to(box, DOWN, buff=0.4)\n        self.play(Create(box), FadeIn(result_text, shift=UP * 0.3), run_time=1.2)\n        self.wait(0.8)\n\n        # Hold final content visible for compositor\n        self.wait(2)"
        }
    ]
}

--- EXAMPLE 3: Diagram scene — shows mid-scene text replacement ---
Narration: "So here's how it works. We got 16 numbers sorted in a row.
Check the middle — is 8 our target? Nope, 11 is bigger. Throw away the
entire left half. Boom, half the work gone in one shot."
Scene type: diagram, Duration: 22s

Code:
{
    "scenes": [
        {
            "scene_index": 1,
            "manim_code": "from manim import *\nimport numpy as np\n\nclass Scene001(MovingCameraScene):\n    def construct(self):\n        # Title\n        title = Text(\"Binary Search: Step by Step\", font_size=44, weight=BOLD, color=GOLD)\n        title.move_to(UP * 3.2)\n        self.play(Write(title), run_time=1.0)\n\n        # Build array of 16 boxes\n        boxes = VGroup()\n        values = list(range(1, 17))\n        for v in values:\n            rect = RoundedRectangle(corner_radius=0.1, width=0.7, height=0.7, color=BLUE)\n            label = Text(str(v), font_size=20)\n            label.move_to(rect.get_center())\n            boxes.add(VGroup(rect, label))\n        boxes.arrange(RIGHT, buff=0.08)\n        boxes.set_width(min(boxes.get_width(), 12.0))\n        boxes.move_to(DOWN * 0.3)\n        self.play(LaggedStart(*[FadeIn(b, shift=UP * 0.3) for b in boxes], lag_ratio=0.05), run_time=1.5)\n        self.wait(0.5)\n\n        # Target label — positioned above boxes\n        target = Text(\"Target: 11\", font_size=32, color=YELLOW)\n        target.next_to(boxes, UP, buff=0.5)\n        self.play(FadeIn(target, shift=DOWN * 0.3), run_time=0.9)\n\n        # Highlight middle element\n        mid_box = boxes[7]\n        highlight = SurroundingRectangle(mid_box, color=YELLOW, buff=0.05)\n        mid_label = Text(\"Middle: 8\", font_size=24, color=YELLOW)\n        mid_label.next_to(mid_box, DOWN, buff=0.4)\n        self.play(Create(highlight), FadeIn(mid_label), run_time=1.0)\n        self.wait(0.5)\n\n        # FadeOut mid_label BEFORE showing compare text in same region (overlap prevention)\n        self.play(FadeOut(mid_label), run_time=0.4)\n        compare = Text(\"11 > 8 → discard left half\", font_size=28, color=RED)\n        compare.next_to(boxes, DOWN, buff=0.6)\n        self.play(FadeIn(compare, shift=UP * 0.3), run_time=1.0)\n        left_half = VGroup(*boxes[:8])\n        self.play(left_half.animate.set_opacity(0.2), FadeOut(highlight), run_time=1.2)\n        self.wait(0.8)\n\n        # Hold final content visible for compositor\n        self.wait(2)"
        }
    ]
}

--- EXAMPLE 4: Summary scene — shows progressive reveal without overlap ---
Narration: "So remember, the derivative is your ability to read the game
in real time. It tells you exactly how fast things are changing. Master this
fundamental, and everything in calculus builds from here."
Scene type: summary, Duration: 20s

Code:
{
    "scenes": [
        {
            "scene_index": 4,
            "manim_code": "from manim import *\nimport numpy as np\n\nclass Scene004(MovingCameraScene):\n    def construct(self):\n        # Title\n        title = Text(\"Key Takeaways\", font_size=44, weight=BOLD, color=GOLD)\n        title.move_to(UP * 3.2)\n        self.play(Write(title), run_time=1.0)\n\n        # Build bullet points using VGroup.arrange() for automatic spacing (no manual overlap)\n        bullets_data = [\n            \"Derivative = instantaneous rate of change\",\n            \"Power Rule: xⁿ → nxⁿ⁻¹\",\n            \"Tangent line slope at any point\",\n        ]\n        bullets = VGroup()\n        for text in bullets_data:\n            rect = RoundedRectangle(corner_radius=0.15, width=9, height=0.8, color=BLUE, fill_opacity=0.1)\n            label = Text(text, font_size=28, color=WHITE)\n            label.set_width(min(label.width, 8.0))\n            label.move_to(rect.get_center())\n            bullets.add(VGroup(rect, label))\n        bullets.arrange(DOWN, buff=0.4)\n        bullets.move_to(DOWN * 0.3)\n        bullets.set_height(min(bullets.get_height(), 4.8))\n\n        # Reveal with LaggedStart — items are pre-arranged, no overlap\n        self.play(\n            LaggedStart(*[FadeIn(b, shift=UP * 0.3) for b in bullets], lag_ratio=0.3),\n            run_time=2.0,\n        )\n        self.wait(1.0)\n\n        # Highlight key point\n        self.play(Indicate(bullets[0], color=YELLOW, scale_factor=1.05), run_time=1.2)\n        self.wait(0.5)\n\n        # Clear bullets BEFORE showing outro text (overlap prevention)\n        self.play(*[FadeOut(b) for b in bullets], run_time=0.8)\n\n        # Final message — now has clear space\n        outro = Text(\"Master the fundamentals!\", font_size=36, color=GREEN_B)\n        outro.move_to(DOWN * 0.3)\n        self.play(FadeIn(outro, shift=UP * 0.3), run_time=1.0)\n        self.wait(1.0)\n\n        # Hold final content visible for compositor\n        self.wait(2)"
        }
    ]
}

--- EXAMPLE 5: Geometry scene — shapes with Text labels via .next_to() ---
Narration: "Let's look at the key shapes in geometry. A circle is defined by
its radius. A hexagon is a regular polygon with six sides. Each shape has
its own area formula — notice how they're all built from the same principles."
Scene type: geometry, Duration: 22s

Code:
{
    "scenes": [
        {
            "scene_index": 2,
            "manim_code": "from manim import *\nimport numpy as np\n\nclass Scene002(MovingCameraScene):\n    def construct(self):\n        title = Text(\"Core Geometric Shapes\", font_size=44, weight=BOLD, color=GOLD)\n        title.move_to(UP * 3.2)\n        self.play(Write(title), run_time=1.0)\n\n        # Circle with radius label — label positioned via .next_to(), no overlap\n        circle = Circle(radius=1.2, color=BLUE, fill_opacity=0.15)\n        circle.move_to(LEFT * 3.5)\n        radius_line = Line(circle.get_center(), circle.get_right(), color=YELLOW)\n        radius_label = Text(\"r\", font_size=28, color=YELLOW)\n        radius_label.next_to(radius_line, UP, buff=0.15)\n        circ_formula = Text(\"A = πr²\", font_size=28, color=BLUE)\n        circ_formula.next_to(circle, DOWN, buff=0.5)\n        self.play(Create(circle), Create(radius_line), FadeIn(radius_label), run_time=1.5)\n        self.play(FadeIn(circ_formula, shift=UP * 0.3), run_time=1.0)\n        self.wait(0.5)\n\n        # Hexagon with side label — label positioned away from circle, no overlap\n        hex_shape = RegularPolygon(n=6, radius=1.2, color=GREEN, fill_opacity=0.15)\n        hex_shape.move_to(RIGHT * 1.5)\n        side_label = Text(\"s\", font_size=28, color=GREEN)\n        # Position label on the top-right edge of hexagon, not floating\n        edge_mid = (hex_shape.get_vertices()[0] + hex_shape.get_vertices()[1]) / 2\n        side_label.move_to(edge_mid + RIGHT * 0.3 + UP * 0.15)\n        hex_formula = Text(\"A = (3√3/2)s²\", font_size=26, color=GREEN)\n        hex_formula.next_to(hex_shape, DOWN, buff=0.5)\n        self.play(Create(hex_shape), FadeIn(side_label), run_time=1.5)\n        self.play(FadeIn(hex_formula, shift=UP * 0.3), run_time=1.0)\n        self.wait(0.5)\n\n        # Highlight area formula pattern — FadeOut previous formulas first (overlap prevention)\n        self.play(FadeOut(circ_formula), FadeOut(hex_formula), FadeOut(radius_label), FadeOut(side_label), run_time=0.8)\n        self.play(FadeOut(radius_line), run_time=0.5)\n\n        insight = Text(\"All area formulas scale with size²\", font_size=32, color=YELLOW)\n        insight.move_to(DOWN * 1.8)\n        insight.set_width(min(insight.width, 8.5))\n        self.play(FadeIn(insight, shift=UP * 0.3), run_time=1.2)\n        self.play(Indicate(circle, color=BLUE, scale_factor=1.05), run_time=1.0)\n        self.play(Indicate(hex_shape, color=GREEN, scale_factor=1.05), run_time=1.0)\n        self.wait(2)"
        }
    ]
}

--- EXAMPLE 6: Concept reveal with cards — RoundedRectangle + Text via VGroup.arrange ---
Narration: "Here are the three laws of thermodynamics. First: energy cannot
be created or destroyed. Second: entropy always increases. Third: absolute zero
is unreachable. Each law builds on the last to define the limits of our universe."
Scene type: concept_reveal, Duration: 24s

Code:
{
    "scenes": [
        {
            "scene_index": 1,
            "manim_code": "from manim import *\nimport numpy as np\n\nclass Scene001(MovingCameraScene):\n    def construct(self):\n        title = Text(\"Laws of Thermodynamics\", font_size=44, weight=BOLD, color=GOLD)\n        title.move_to(UP * 3.2)\n        self.play(Write(title), run_time=1.0)\n\n        # Build law cards using VGroup.arrange — automatic spacing, zero overlap risk\n        laws = [\n            (\"1st Law\", \"Energy is conserved\", BLUE),\n            (\"2nd Law\", \"Entropy always increases\", GREEN),\n            (\"3rd Law\", \"Absolute zero is unreachable\", TEAL),\n        ]\n        cards = VGroup()\n        for law_num, description, color in laws:\n            card = VGroup()\n            bg = RoundedRectangle(corner_radius=0.2, width=9.5, height=1.1,\n                                   color=color, fill_opacity=0.12, stroke_width=2)\n            num_text = Text(law_num, font_size=30, color=color, weight=BOLD)\n            num_text.set_width(min(num_text.width, 2.0))\n            desc_text = Text(description, font_size=27, color=WHITE)\n            desc_text.set_width(min(desc_text.width, 6.8))\n            # Arrange number and description side by side within card\n            inner = VGroup(num_text, desc_text)\n            inner.arrange(RIGHT, buff=0.5)\n            inner.move_to(bg.get_center())\n            card.add(bg, inner)\n            cards.add(card)\n        cards.arrange(DOWN, buff=0.35)\n        cards.move_to(DOWN * 0.3)\n        cards.set_height(min(cards.get_height(), 5.0))\n\n        # Reveal cards one by one with LaggedStart — pre-arranged, no overlap\n        self.play(\n            LaggedStart(*[FadeIn(c, shift=RIGHT * 0.4) for c in cards], lag_ratio=0.4),\n            run_time=2.0,\n        )\n        self.wait(0.8)\n\n        # Highlight each law sequentially — Indicate pulses without moving\n        for card in cards:\n            self.play(Indicate(card, color=YELLOW, scale_factor=1.03), run_time=1.0)\n            self.wait(0.3)\n\n        # Final emphasis on the pattern\n        pattern = Text(\"Each law defines a universal limit\", font_size=30, color=YELLOW)\n        pattern.next_to(cards, DOWN, buff=0.5)\n        pattern.set_width(min(pattern.width, 8.5))\n        self.play(FadeIn(pattern, shift=UP * 0.3), run_time=1.0)\n        self.wait(2)"
        }
    ]
}

--- EXAMPLE 7: Graph with two functions + area shading (axes.get_area) ---
Narration: "The integral of a function is the area under its curve. Here we see
f of x equals x squared and g of x equals x. The shaded region between them
from zero to one represents the difference in their integrals — exactly one sixth."
Scene type: graph, Duration: 26s

Code:
{
    "scenes": [
        {
            "scene_index": 2,
            "manim_code": "from manim import *\nimport numpy as np\n\nclass Scene002(MovingCameraScene):\n    def construct(self):\n        title = Text(\"Area Between Two Curves\", font_size=44, weight=BOLD, color=GOLD)\n        title.move_to(UP * 3.2)\n        self.play(Write(title), run_time=1.0)\n\n        axes = Axes(\n            x_range=[-0.3, 1.5, 0.5], y_range=[-0.2, 1.6, 0.5],\n            x_length=7, y_length=5,\n            axis_config={\"include_numbers\": True},\n        ).move_to(DOWN * 0.3)\n        # MUST use Text() for axis labels — plain strings crash with LaTeX error\n        x_lab = axes.get_x_axis_label(Text(\"x\", font_size=28))\n        y_lab = axes.get_y_axis_label(Text(\"y\", font_size=28))\n        self.play(Create(axes), Write(x_lab), Write(y_lab), run_time=1.5)\n\n        # Plot f(x) = x² in blue\n        graph_f = axes.plot(lambda x: x**2, color=BLUE, x_range=[0, 1.4])\n        label_f = Text(\"f(x) = x²\", color=BLUE, font_size=28)\n        label_f.next_to(axes.c2p(1.2, 1.44), RIGHT, buff=0.15)\n        label_f.set_width(min(label_f.width, 3.0))\n        self.play(Create(graph_f), FadeIn(label_f, shift=UP * 0.2), run_time=1.5)\n        self.wait(0.4)\n\n        # Plot g(x) = x in green\n        graph_g = axes.plot(lambda x: x, color=GREEN, x_range=[0, 1.4])\n        label_g = Text(\"g(x) = x\", color=GREEN, font_size=28)\n        label_g.next_to(axes.c2p(1.2, 1.2), LEFT, buff=0.5)\n        label_g.set_width(min(label_g.width, 3.0))\n        self.play(Create(graph_g), FadeIn(label_g, shift=UP * 0.2), run_time=1.5)\n        self.wait(0.5)\n\n        # Shade area between curves using get_area — bounded region [0, 1]\n        area = axes.get_area(\n            graph_g, x_range=[0, 1], bounded_graph=graph_f,\n            color=YELLOW, opacity=0.35,\n        )\n        self.play(FadeIn(area), run_time=1.2)\n        self.wait(0.5)\n\n        # FadeOut labels before showing formula (overlap prevention)\n        self.play(FadeOut(label_f), FadeOut(label_g), run_time=0.6)\n\n        # Show result formula in clear space\n        result = Text(\"∫₀¹ (x - x²) dx = 1/6\", font_size=32, color=YELLOW)\n        result.set_width(min(result.width, 8.5))\n        result.move_to(UP * 1.8 + RIGHT * 2.5)\n        self.play(FadeIn(result, shift=DOWN * 0.3), run_time=1.2)\n        box = SurroundingRectangle(result, color=YELLOW, buff=0.12)\n        self.play(Create(box), run_time=1.0)\n        self.wait(2)"
        }
    ]
}

--- EXAMPLE 8: Tree diagram using Graph() with Text labels (LaTeX trap prevention) ---
Narration: "A binary search tree organizes data hierarchically. The root is 8.
Values less than 8 go left, greater go right. This structure allows us to find
any value in just log n comparisons — far faster than a linear search."
Scene type: diagram, Duration: 22s

Code:
{
    "scenes": [
        {
            "scene_index": 3,
            "manim_code": "from manim import *\nimport numpy as np\n\nclass Scene003(MovingCameraScene):\n    def construct(self):\n        title = Text(\"Binary Search Tree\", font_size=44, weight=BOLD, color=GOLD)\n        title.move_to(UP * 3.2)\n        self.play(Write(title), run_time=1.0)\n\n        # Build BST using Graph with tree layout\n        # CRITICAL: labels MUST be {v: Text(...)} dict — labels=True crashes with LaTeX!\n        vertices = [8, 3, 12, 1, 5, 10, 15]\n        edges = [(8,3), (8,12), (3,1), (3,5), (12,10), (12,15)]\n        vertex_labels = {v: Text(str(v), font_size=22, color=WHITE) for v in vertices}\n        tree = Graph(\n            vertices, edges,\n            labels=vertex_labels,\n            layout=\"tree\",\n            root_vertex=8,\n            vertex_config={\"color\": BLUE, \"radius\": 0.35, \"fill_opacity\": 0.8},\n            edge_config={\"color\": GREY, \"stroke_width\": 2},\n        )\n        tree.move_to(DOWN * 0.5)\n        tree.set_height(min(tree.get_height(), 4.5))\n        self.play(Create(tree), run_time=2.0)\n        self.wait(0.5)\n\n        # Highlight root node\n        root_indicator = Text(\"Root: 8\", font_size=28, color=GOLD)\n        root_indicator.next_to(tree.vertices[8], UP, buff=0.5)\n        root_indicator.set_width(min(root_indicator.width, 3.0))\n        self.play(Indicate(tree.vertices[8], color=GOLD, scale_factor=1.3), run_time=1.0)\n        self.play(FadeIn(root_indicator, shift=DOWN * 0.2), run_time=0.8)\n        self.wait(0.4)\n\n        # Show left < right rule — FadeOut root indicator first (overlap prevention)\n        self.play(FadeOut(root_indicator), run_time=0.5)\n        left_label = Text(\"< 8\", font_size=26, color=GREEN)\n        right_label = Text(\"> 8\", font_size=26, color=RED)\n        left_label.next_to(tree.vertices[3], LEFT, buff=0.4)\n        right_label.next_to(tree.vertices[12], RIGHT, buff=0.4)\n        self.play(FadeIn(left_label), FadeIn(right_label), run_time=1.0)\n        self.play(\n            Indicate(tree.vertices[3], color=GREEN, scale_factor=1.2),\n            Indicate(tree.vertices[12], color=RED, scale_factor=1.2),\n            run_time=1.2,\n        )\n        self.wait(0.5)\n\n        # Complexity note\n        self.play(FadeOut(left_label), FadeOut(right_label), run_time=0.6)\n        complexity = Text(\"Search time: O(log n)\", font_size=30, color=YELLOW)\n        complexity.set_width(min(complexity.width, 8.5))\n        complexity.move_to(UP * 1.5)\n        self.play(FadeIn(complexity, shift=DOWN * 0.3), run_time=1.0)\n        box = SurroundingRectangle(complexity, color=YELLOW, buff=0.12)\n        self.play(Create(box), run_time=1.0)\n        self.wait(2)"
        }
    ]
}
"""
