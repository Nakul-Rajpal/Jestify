"""Service for generating educational scripts using the Anthropic Claude API."""

import json
import logging
from typing import Optional

import anthropic

from shared.contracts.character_schema import CHARACTER_PERSONALITIES
from shared.contracts.enums import Character, Difficulty
from shared.contracts.pipeline_schema import GeneratedScript

from ..config import settings

logger = logging.getLogger(__name__)

# Model to use for script generation
CLAUDE_MODEL = "claude-sonnet-4-20250514"

# Difficulty-specific instructions
DIFFICULTY_INSTRUCTIONS: dict[Difficulty, str] = {
    Difficulty.BEGINNER: (
        "Explain concepts at a beginner level. Use simple language, avoid jargon, "
        "and break down ideas into the most fundamental building blocks. "
        "Assume no prior knowledge of the topic."
    ),
    Difficulty.INTERMEDIATE: (
        "Explain concepts at an intermediate level. You can use some technical terms "
        "but always briefly clarify them. Build on foundational knowledge and make "
        "connections between concepts."
    ),
    Difficulty.ADVANCED: (
        "Explain concepts at an advanced level. Use proper technical terminology, "
        "explore nuances, edge cases, and deeper implications. Assume a solid "
        "foundation in the subject area."
    ),
}

# Available ManimGL scene types for the LLM to choose from
AVAILABLE_SCENE_TYPES = """
Available ManimGL scene types you can use:
- "equation": Display and animate mathematical equations (LaTeX). Parameters: {"latex": "E = mc^2", "steps": ["step1_latex", "step2_latex"]}
- "graph": Plot a mathematical function or data. Parameters: {"function": "x**2", "x_range": [-5, 5], "y_range": [0, 25], "labels": {"x": "x", "y": "f(x)"}}
- "diagram": Show a conceptual diagram with labeled nodes and edges. Parameters: {"nodes": [{"label": "A", "position": [0, 0]}], "edges": [{"from": "A", "to": "B"}]}
- "text": Display key text points with animations. Parameters: {"title": "Key Concept", "bullets": ["Point 1", "Point 2"]}
- "geometry": Show geometric shapes and transformations. Parameters: {"shapes": [{"type": "circle", "radius": 1}], "transformations": ["rotate", "scale"]}
"""


class ScriptGenerator:
    """Generates structured educational scripts using Claude."""

    def __init__(self) -> None:
        self.client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    def generate(
        self,
        extracted_text: str,
        character: Character,
        difficulty: Difficulty,
        user_prompt: Optional[str] = None,
    ) -> GeneratedScript:
        """
        Generate an educational script from the provided text.

        Args:
            extracted_text: The source material text extracted from documents.
            character: The character persona to use.
            difficulty: The difficulty level for the explanation.
            user_prompt: Optional additional instructions from the user.

        Returns:
            A GeneratedScript with structured scene instructions.
        """
        personality = CHARACTER_PERSONALITIES[character]
        difficulty_instruction = DIFFICULTY_INSTRUCTIONS[difficulty]

        system_prompt = self._build_system_prompt(personality, difficulty_instruction)
        user_message = self._build_user_message(extracted_text, user_prompt)

        logger.info(
            f"Generating script: character={character.value}, "
            f"difficulty={difficulty.value}, text_length={len(extracted_text)}"
        )

        response = self.client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )

        # Extract the text content from the response
        response_text = response.content[0].text

        # Parse the JSON from the response
        script_data = self._parse_response(response_text)

        # Ensure character and difficulty are set correctly
        script_data["character"] = character.value
        script_data["difficulty"] = difficulty.value

        return GeneratedScript(**script_data)

    def _build_system_prompt(self, personality, difficulty_instruction: str) -> str:
        """Build the system prompt with character personality and instructions."""
        return f"""You are an educational content script writer. Your job is to create engaging, \
educational video scripts that will be animated using ManimGL (a math animation library).

CHARACTER PERSONA:
- Name: {personality.display_name}
- Voice Style: {personality.voice_style}
- Analogy Domain: {personality.analogy_domain}
- Catchphrases: {', '.join(personality.catchphrases)}
- Tone: {personality.tone}

You MUST write all narration text in the voice and style of this character. Use their catchphrases \
naturally, draw analogies from their domain, and maintain their tone throughout.

DIFFICULTY LEVEL:
{difficulty_instruction}

{AVAILABLE_SCENE_TYPES}

OUTPUT FORMAT:
You must respond with ONLY a valid JSON object (no markdown, no extra text) with this exact structure:
{{
    "title": "A catchy educational title",
    "total_scenes": <number of scenes>,
    "scenes": [
        {{
            "scene_index": 0,
            "narration_text": "What the character says during this scene",
            "manim_scene_type": "equation|graph|diagram|text|geometry",
            "manim_parameters": {{ ... parameters specific to the scene type ... }},
            "duration_hint_seconds": 10.0,
            "character_action": "talking|pointing|idle"
        }}
    ],
    "intro_text": "An engaging introduction by the character",
    "outro_text": "A memorable closing by the character"
}}

GUIDELINES:
- Create 4-8 scenes that progressively build understanding
- Each scene should focus on ONE concept or step
- Narration should be 2-4 sentences per scene
- Use the character's voice consistently
- Choose the most appropriate scene type for each concept
- Include at least one equation or graph scene if the content involves math/science
- The intro should hook the viewer and the outro should summarize key takeaways
"""

    def _build_user_message(self, extracted_text: str, user_prompt: Optional[str]) -> str:
        """Build the user message with source material and optional instructions."""
        message = f"""Please create an educational video script based on the following source material:

--- SOURCE MATERIAL ---
{extracted_text}
--- END SOURCE MATERIAL ---
"""
        if user_prompt:
            message += f"""
Additional instructions from the user:
{user_prompt}
"""

        message += """
Remember: respond with ONLY the JSON object, no markdown code fences or extra text.
"""
        return message

    def _parse_response(self, response_text: str) -> dict:
        """Parse the LLM response text into a dictionary."""
        # Try to extract JSON from the response
        text = response_text.strip()

        # Remove markdown code fences if present
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]

        text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.error(f"Response text: {text[:500]}")
            raise ValueError(f"LLM did not return valid JSON: {e}")
