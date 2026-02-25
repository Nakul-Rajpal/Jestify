"""Service for classifying completed videos into subjects and topics using Claude."""

import json
import logging
import uuid
from typing import Optional

import anthropic
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models.job import Job
from ..models.subject import Subject
from ..models.topic import Topic

logger = logging.getLogger(__name__)

CLAUDE_MODEL = "claude-sonnet-4-20250514"


class TopicClassifier:
    """Classifies completed videos into subjects and topics."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    async def classify_job(self, job: Job) -> Optional[Topic]:
        """
        Classify a completed job into a subject and topic.

        1. Extract title + narrations from script_json, excerpts from documents
        2. Call Claude to determine subject_name, topic_name
        3. Find-or-create Subject and Topic with correct sort_order
        4. Link the Job to the Topic

        Returns the Topic, or None if classification fails.
        """
        if not job.script_json:
            logger.warning(f"Job {job.id} has no script_json, skipping classification")
            return None

        script = job.script_json
        title = script.get("title", "")
        intro_text = script.get("intro_text", "")
        narrations = []
        for scene in script.get("scenes", []):
            narration = scene.get("narration_text", "")
            if narration:
                narrations.append(narration)

        document_excerpts = []
        if job.documents:
            for doc in job.documents:
                if doc.extracted_text:
                    document_excerpts.append(doc.extracted_text[:500])

        classification = self._classify_with_claude(
            title=title,
            intro_text=intro_text,
            narrations=narrations,
            document_excerpts=document_excerpts,
        )

        if not classification:
            return None

        subject_name = classification["subject_name"]
        topic_name = classification["topic_name"]
        topic_description = classification.get("topic_description", "")

        subject = await self._find_or_create_subject(subject_name)

        topic = await self._find_or_create_topic(
            subject=subject,
            topic_name=topic_name,
            topic_description=topic_description,
        )

        job.topic_id = topic.id
        await self.db.flush()

        logger.info(
            f"Classified job {job.id}: subject='{subject.name}', "
            f"topic='{topic.name}' (sort_order={topic.sort_order})"
        )
        return topic

    def _classify_with_claude(
        self,
        title: str,
        intro_text: str,
        narrations: list[str],
        document_excerpts: list[str],
    ) -> Optional[dict]:
        """Call Claude to classify the video content into a subject and topic."""
        narrations_text = "\n".join(f"- {n}" for n in narrations[:5])
        excerpts_text = "\n---\n".join(document_excerpts[:3])

        prompt = f"""\
Analyze this educational video content and classify it into a subject and topic.

VIDEO TITLE: {title}
INTRODUCTION: {intro_text}
SCENE NARRATIONS:
{narrations_text}

SOURCE DOCUMENT EXCERPTS:
{excerpts_text}

You must respond with ONLY a valid JSON object (no markdown, no extra text):
{{
    "subject_name": "The academic subject (e.g., 'Calculus 2', 'Linear Algebra', 'Discrete Mathematics')",
    "topic_name": "The specific topic within that subject (e.g., 'Antiderivatives', 'Eigenvalues', 'Graph Theory')",
    "topic_description": "A brief 1-sentence description of what this topic covers"
}}

RULES:
- subject_name should be a standard academic course name
- topic_name should be a specific, well-known topic within that course
- For math subjects, use standard course names: "Calculus 1", "Calculus 2", "Calculus 3", "Linear Algebra", "Differential Equations", "Discrete Mathematics", "Statistics", "Probability", "Real Analysis", "Abstract Algebra", etc.
- Keep names concise and canonical
"""
        # Split into system prompt (cacheable) and user message
        system_prompt = (
            "You are an expert academic classifier. Given educational video content, "
            "classify it into a subject and topic. Respond with ONLY valid JSON."
        )
        try:
            response = self.client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=500,
                system=[
                    {
                        "type": "text",
                        "text": system_prompt,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[{"role": "user", "content": prompt}],
            )
            cache_read = getattr(response.usage, "cache_read_input_tokens", 0)
            cache_create = getattr(response.usage, "cache_creation_input_tokens", 0)
            logger.info(
                "Classification usage: input=%d, output=%d, cache_read=%d, cache_creation=%d",
                response.usage.input_tokens,
                response.usage.output_tokens,
                cache_read,
                cache_create,
            )
            text = response.content[0].text.strip()

            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

            return json.loads(text)
        except Exception as e:
            logger.error(f"Claude classification failed: {e}")
            return None

    async def _find_or_create_subject(self, name: str) -> Subject:
        """Find an existing subject by name (case-insensitive), or create a new one."""
        result = await self.db.execute(
            select(Subject).where(func.lower(Subject.name) == name.lower())
        )
        subject = result.scalar_one_or_none()

        if subject is None:
            subject = Subject(
                id=uuid.uuid4(),
                name=name,
                category="math",
            )
            self.db.add(subject)
            await self.db.flush()
            logger.info(f"Created new subject: '{name}'")

        return subject

    async def _find_or_create_topic(
        self,
        subject: Subject,
        topic_name: str,
        topic_description: str,
    ) -> Topic:
        """Find an existing topic within a subject, or create with correct sort_order."""
        result = await self.db.execute(
            select(Topic).where(
                Topic.subject_id == subject.id,
                func.lower(Topic.name) == topic_name.lower(),
            )
        )
        topic = result.scalar_one_or_none()

        if topic is not None:
            return topic

        # Determine sort_order relative to existing topics
        existing_result = await self.db.execute(
            select(Topic)
            .where(Topic.subject_id == subject.id)
            .order_by(Topic.sort_order)
        )
        existing_topics = existing_result.scalars().all()

        if not existing_topics:
            sort_order = 10
        else:
            sort_order = self._determine_sort_order(
                subject_name=subject.name,
                new_topic=topic_name,
                existing_topics=[(t.name, t.sort_order) for t in existing_topics],
            )

        topic = Topic(
            id=uuid.uuid4(),
            name=topic_name,
            subject_id=subject.id,
            sort_order=sort_order,
            description=topic_description,
        )
        self.db.add(topic)
        await self.db.flush()
        logger.info(
            f"Created new topic: '{topic_name}' in '{subject.name}' "
            f"with sort_order={sort_order}"
        )
        return topic

    def _determine_sort_order(
        self,
        subject_name: str,
        new_topic: str,
        existing_topics: list[tuple[str, int]],
    ) -> int:
        """Ask Claude where the new topic fits pedagogically among existing topics."""
        topics_list = "\n".join(
            f"  {order}: {name}" for name, order in existing_topics
        )

        prompt = f"""\
In the academic subject "{subject_name}", the following topics already exist with \
their pedagogical sort order (lower numbers = learned earlier):

{topics_list}

A new topic "{new_topic}" needs to be placed in the correct pedagogical position.

Where should it go? Respond with ONLY a JSON object:
{{
    "sort_order": <integer>
}}

The sort_order should reflect when this topic is typically taught relative to the \
existing topics. Use integers with gaps (multiples of 10) so future insertions are easy.
If it should come before all existing topics, use a number lower than the lowest.
If after all, use a number higher than the highest.
If between two topics, use a number between them.
"""
        sort_system = (
            "You are an expert in academic curriculum ordering. "
            "Given existing topics and a new topic, determine the correct "
            "pedagogical sort order. Respond with ONLY valid JSON."
        )
        try:
            response = self.client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=100,
                system=[
                    {
                        "type": "text",
                        "text": sort_system,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

            result = json.loads(text)
            return result["sort_order"]
        except Exception as e:
            logger.warning(f"Failed to determine sort_order, using max+10: {e}")
            if existing_topics:
                return max(order for _, order in existing_topics) + 10
            return 10
