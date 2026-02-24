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
"""
