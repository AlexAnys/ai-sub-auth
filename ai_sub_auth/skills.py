"""Meta Skill Framework — 8 universal AI skills for any application.

Any AI feature in any application is a composition of these 8 meta skills.
Agents use this framework to discover, suggest, and implement AI integrations.

Usage:
    from ai_sub_auth.skills import META_SKILLS, suggest_for_app, AppProfile

    profile = AppProfile(
        domain="note-taking",
        verbs=["create notes", "search", "tag", "link"],
        nouns=["notes", "tags", "folders", "backlinks"],
        roles=["user"],
        existing_ai=[],
    )
    suggestions = suggest_for_app(profile)
    # Returns 3 ranked (skill, reason, effort) tuples
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Skill(Enum):
    """The 8 meta skills — every AI feature is one of these."""
    SUMMARIZE = "summarize"     # many → few
    GENERATE  = "generate"      # few → many
    ANALYZE   = "analyze"       # raw → insight
    TRANSFORM = "transform"     # form A → form B
    CLASSIFY  = "classify"      # items → buckets
    EVALUATE  = "evaluate"      # content → score
    CONVERSE  = "converse"      # user ↔ AI
    EXTRACT   = "extract"       # noise → signal


@dataclass(frozen=True)
class MetaSkill:
    """A meta skill definition with trigger signals for auto-detection."""
    skill: Skill
    name: str
    direction: str
    description: str
    triggers: tuple[str, ...]   # signals that indicate this skill applies


META_SKILLS: tuple[MetaSkill, ...] = (
    MetaSkill(
        skill=Skill.SUMMARIZE,
        name="Summarize",
        direction="many → few",
        description="Reduce volume while preserving meaning",
        triggers=("collection", "list", "history", "archive", "thread",
                  "log", "notes", "inbox", "feed", "timeline"),
    ),
    MetaSkill(
        skill=Skill.GENERATE,
        name="Generate",
        direction="few → many",
        description="Produce new content from intent or spec",
        triggers=("create", "new", "editor", "blank", "template",
                  "compose", "draft", "write", "scaffold", "boilerplate"),
    ),
    MetaSkill(
        skill=Skill.ANALYZE,
        name="Analyze",
        direction="raw → insight",
        description="Find patterns, anomalies, trends in data",
        triggers=("chart", "dashboard", "table", "metrics", "data",
                  "report", "statistics", "numbers", "time-series", "graph"),
    ),
    MetaSkill(
        skill=Skill.TRANSFORM,
        name="Transform",
        direction="form A → form B",
        description="Convert between formats, styles, languages",
        triggers=("export", "import", "convert", "translate", "format",
                  "migrate", "render", "compile", "publish", "adapt"),
    ),
    MetaSkill(
        skill=Skill.CLASSIFY,
        name="Classify",
        direction="items → buckets",
        description="Assign categories, priorities, or labels",
        triggers=("inbox", "queue", "tag", "label", "sort",
                  "filter", "priority", "category", "triage", "route"),
    ),
    MetaSkill(
        skill=Skill.EVALUATE,
        name="Evaluate",
        direction="content → score",
        description="Judge quality against criteria",
        triggers=("review", "grade", "check", "rubric", "quality",
                  "feedback", "score", "approve", "reject", "lint"),
    ),
    MetaSkill(
        skill=Skill.CONVERSE,
        name="Converse",
        direction="user ↔ AI",
        description="Multi-turn contextual dialogue",
        triggers=("chat", "help", "support", "assistant", "guide",
                  "onboard", "tutorial", "explain", "ask", "Q&A"),
    ),
    MetaSkill(
        skill=Skill.EXTRACT,
        name="Extract",
        direction="noise → signal",
        description="Pull structured data from unstructured input",
        triggers=("form", "input", "upload", "paste", "parse",
                  "OCR", "voice", "scan", "entry", "import"),
    ),
)


@dataclass
class AppProfile:
    """Profile of a target application — built by an agent during SCAN phase."""
    domain: str
    verbs: list[str] = field(default_factory=list)
    nouns: list[str] = field(default_factory=list)
    roles: list[str] = field(default_factory=list)
    existing_ai: list[str] = field(default_factory=list)


@dataclass
class Suggestion:
    """A ranked AI integration suggestion."""
    skill: MetaSkill
    reason: str
    effort: str         # "quick_win" | "moderate" | "deep"
    score: float


def suggest_for_app(profile: AppProfile, top_n: int = 3) -> list[Suggestion]:
    """Score all meta skills against an app profile and return top N suggestions.

    This implements the MATCH + RANK steps of the 3-Suggestion Protocol.
    Agents can use this programmatically or follow AGENT.md manually.
    """
    all_words = " ".join(profile.verbs + profile.nouns + [profile.domain]).lower()
    ai_words = " ".join(profile.existing_ai).lower()

    candidates: list[Suggestion] = []

    for ms in META_SKILLS:
        score = 0.0
        matched_triggers = []

        for trigger in ms.triggers:
            if trigger in all_words:
                score += 1.0
                matched_triggers.append(trigger)
                # Greenfield bonus: not already AI-powered
                if trigger not in ai_words:
                    score += 2.0

        if score < 2.0:
            continue

        # Estimate effort by how many triggers match (more = easier)
        effort = "quick_win" if len(matched_triggers) >= 3 else "moderate" if len(matched_triggers) >= 2 else "deep"

        reason = f"App has [{', '.join(matched_triggers[:3])}] — ideal for {ms.name}"
        candidates.append(Suggestion(skill=ms, reason=reason, effort=effort, score=score))

    # Sort by score descending
    candidates.sort(key=lambda s: s.score, reverse=True)

    # Enforce diversity: no two suggestions with the same skill
    seen_skills = set()
    diverse: list[Suggestion] = []
    for c in candidates:
        if c.skill.skill not in seen_skills:
            diverse.append(c)
            seen_skills.add(c.skill.skill)
        if len(diverse) >= top_n:
            break

    # Enforce: at least one quick_win if possible
    efforts = {s.effort for s in diverse}
    if "quick_win" not in efforts and len(diverse) >= top_n:
        for c in candidates:
            if c.effort == "quick_win" and c.skill.skill not in seen_skills:
                seen_skills.discard(diverse[-1].skill.skill)
                diverse[-1] = c
                seen_skills.add(c.skill.skill)
                break

    return diverse
