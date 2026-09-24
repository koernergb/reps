"""Interviewer turns: LLM-backed when configured, deterministic policy otherwise.

Both paths return the same `InterviewerTurn` shape. The server validates the recommended
transition and the learner event classification, then passes the message through the guard.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field

from app.corpus.loader import LoadedProblem
from app.interview.events import LEARNER_UTTERANCES
from app.interview.policy import ModePolicy
from app.interview.state_machine import TRANSITIONS, State
from app.llm.prompts import fence, load_prompt
from app.llm.provider import LLMProvider, LLMResult

PROMPT_VERSION = "v1"
TURN_SCHEMA_VERSION = 1
LearnerEventType = Literal[
    "clarification_asked",
    "reasoning_statement",
    "approach_proposed",
    "approach_changed",
    "complexity_answer",
    "followup_answer",
]


class InterviewerTurn(BaseModel):
    message: str = Field(max_length=1200)
    recommended_transition: State | None
    learner_event_type: LearnerEventType | None
    capability_tags: list[str]


@dataclass
class TurnContext:
    problem: LoadedProblem
    policy: ModePolicy
    state: State
    learner_message: str | None
    transcript: list[tuple[str, str]]
    code: str
    execution_summary: str
    weaknesses: list[str]
    hints_remaining: int
    entering_state: bool = False
    interviewer_turns_in_state: int = 0
    approach_proposed: bool = False
    capability_slugs: list[str] = field(default_factory=list)


STATE_GUIDANCE: dict[str, str] = {
    "INTRO": "Greet briefly and ask for initial thoughts or questions.",
    "CLARIFICATION": "Answer reasonable clarification questions; do not suggest an approach.",
    "APPROACH_DISCUSSION": "Ask them to explain their approach, the data structures, and "
    "tradeoffs. Challenge suspicious reasoning with a question. Do not propose an approach.",
    "IMPLEMENTATION": "Let them code. Respond to direct questions only; avoid interrupting.",
    "TESTING": "Ask which tests and edge cases they would try; let execution results speak.",
    "COMPLEXITY": "Explicitly ask for time and space complexity and probe the justification.",
    "FOLLOW_UP": "Ask one follow-up question, then wrap up.",
    "COMPLETE": "The interview is over. Thank them.",
    "ABANDONED": "The interview was abandoned.",
}

QUESTION_START = re.compile(
    r"^\s*(can|could|should|would|will|is|are|do|does|did|what|how|why|when|where|which|may)\b",
    re.IGNORECASE,
)
CHANGE_WORDS = re.compile(r"\b(instead|actually|switch|rather|better approach|change)\b", re.I)
BIG_O = re.compile(r"o\s*\(\s*([^)]*?)\s*\)", re.IGNORECASE)
WORD = re.compile(r"[a-z0-9]+")
STOPWORDS = {
    "the",
    "a",
    "an",
    "is",
    "are",
    "can",
    "i",
    "it",
    "to",
    "of",
    "be",
    "do",
    "does",
    "we",
    "what",
    "if",
    "in",
    "and",
    "or",
    "for",
    "should",
    "will",
    "there",
    "my",
    "you",
    "that",
}


def is_question(text: str) -> bool:
    return "?" in text or bool(QUESTION_START.match(text))


def classify_learner_message(state: State, text: str, approach_proposed: bool) -> LearnerEventType:
    if state in ("INTRO", "CLARIFICATION") and is_question(text):
        return "clarification_asked"
    if state == "APPROACH_DISCUSSION":
        if is_question(text):
            return "clarification_asked"
        if not approach_proposed:
            return "approach_proposed"
        return "approach_changed" if CHANGE_WORDS.search(text) else "reasoning_statement"
    if state == "COMPLEXITY":
        return "complexity_answer"
    if state == "FOLLOW_UP":
        return "followup_answer"
    if state == "INTRO":
        return "approach_proposed" if len(text.split()) > 8 else "reasoning_statement"
    return "reasoning_statement"


def capability_tags_for(event_type: str, topic: str) -> list[str]:
    return {
        "clarification_asked": ["interview.clarification"],
        "approach_proposed": [f"{topic}.recognition", f"{topic}.invariant"],
        "approach_changed": [f"{topic}.recognition", f"{topic}.invariant"],
        "complexity_answer": [f"{topic}.complexity"],
        "followup_answer": [f"{topic}.transfer"],
        "reasoning_statement": ["interview.communication"],
    }.get(event_type, [])


def normalize_complexity(value: str) -> str:
    text = value.lower().replace(" ", "").replace("*", "").replace("·", "").replace("\u00d7", "")
    return text.replace("^", "").replace("²", "2")


def complexity_claims(text: str) -> list[str]:
    return [normalize_complexity(match) for match in BIG_O.findall(text)]


def assess_complexity(text: str, time_expected: str, space_expected: str) -> tuple[bool, bool]:
    claims = complexity_claims(text)
    expected_time = complexity_claims(time_expected) or [normalize_complexity(time_expected)]
    expected_space = complexity_claims(space_expected) or [normalize_complexity(space_expected)]
    time_ok = bool(claims) and claims[0] in expected_time
    space_ok = len(claims) >= 2 and claims[1] in expected_space
    if not space_ok and len(claims) == 1 and expected_time == expected_space:
        space_ok = time_ok and "space" in text.lower()
    return time_ok, space_ok


def match_clarification(problem: LoadedProblem, question: str) -> str | None:
    asked = {word for word in WORD.findall(question.lower()) if word not in STOPWORDS}
    best: tuple[float, str] | None = None
    for item in problem.definition.clarifications:
        known = {word for word in WORD.findall(item.question.lower()) if word not in STOPWORDS}
        if not asked or not known:
            continue
        score = len(asked & known) / len(known)
        if score >= 0.5 and (best is None or score > best[0]):
            best = (score, item.answer)
    return best[1] if best else None


def entry_message(context: TurnContext) -> str:
    problem = context.problem.definition
    mock = context.policy.mode == "mock"
    minutes = (context.policy.time_limit_s or 0) // 60
    return {
        "INTRO": (
            f"Let's begin: {problem.title}. You have {minutes} minutes. "
            "Please think aloud as you work."
            if mock
            else f"Hi! Today we'll work on {problem.title}. Take a moment to read it. "
            "What questions do you have, and what are your first thoughts?"
        ),
        "CLARIFICATION": "What would you like to clarify?"
        if mock
        else "Sure. What would you like to clarify before you start?",
        "APPROACH_DISCUSSION": "Walk me through your approach before you code.",
        "IMPLEMENTATION": "Go ahead."
        if mock
        else "Sounds good. Go ahead and implement it, and think aloud if you can.",
        "TESTING": "How would you test this?"
        if mock
        else "How would you test this? Which edge cases worry you? Feel free to run it.",
        "COMPLEXITY": "What are the time and space complexity of your solution?",
        "FOLLOW_UP": problem.follow_ups[0],
        "COMPLETE": "Thanks, that's time. I'll put your report together now.",
        "ABANDONED": "No problem, we can stop here.",
    }[context.state]


def policy_turn(context: TurnContext) -> InterviewerTurn:
    """Deterministic interviewer used offline and as the LLM fallback."""
    problem = context.problem.definition
    mock = context.policy.mode == "mock"
    if context.entering_state or context.learner_message is None:
        return InterviewerTurn(
            message=entry_message(context),
            recommended_transition=None,
            learner_event_type=None,
            capability_tags=[],
        )
    text = context.learner_message
    event_type = classify_learner_message(context.state, text, context.approach_proposed)
    tags = capability_tags_for(event_type, problem.topic)
    transition: State | None = None
    if event_type == "clarification_asked":
        answer = match_clarification(context.problem, text)
        if answer:
            message = answer if mock else f"Good question. {answer}"
        else:
            message = (
                "Make a reasonable assumption and state it."
                if mock
                else "That's worth pinning down. What would you assume, and why?"
            )
        if context.state == "INTRO":
            transition = "CLARIFICATION"
    elif context.state in ("INTRO", "CLARIFICATION"):
        message = "Okay. Walk me through the approach you'd take."
        transition = "APPROACH_DISCUSSION"
    elif context.state == "APPROACH_DISCUSSION":
        probes = [
            "What data structure would you use, and what exactly would it store?",
            "What would the time and space complexity of that be?",
            "Can you walk through the first example with that approach?",
        ]
        turn = context.interviewer_turns_in_state
        if mock and turn >= 1:
            message = "Okay. Go ahead when you're ready."
            transition = "IMPLEMENTATION"
        elif turn < len(probes):
            message = probes[turn] if not mock else probes[min(turn, 1)]
        else:
            message = "That sounds reasonable. Go ahead and code it when you're ready."
            transition = "IMPLEMENTATION"
    elif context.state == "IMPLEMENTATION":
        message = "Mm-hm." if mock else "Sounds good. Keep going."
    elif context.state == "TESTING":
        message = (
            "Okay."
            if mock
            else "Good. Are there edge cases, like empty or minimal inputs, you haven't tried?"
        )
    elif context.state == "COMPLEXITY":
        time_ok, space_ok = assess_complexity(
            text, problem.time_complexity, problem.space_complexity
        )
        if time_ok and space_ok:
            message = "That matches my analysis."
            transition = "FOLLOW_UP"
        elif not complexity_claims(text):
            message = "Can you state that in big-O terms for both time and space?"
        elif context.interviewer_turns_in_state >= 2:
            message = "Okay, let's move on."
            transition = "FOLLOW_UP"
        elif mock:
            message = "Are you sure? Walk me through how you got that."
        else:
            which = "time" if not time_ok else "space"
            message = (
                f"Let's double-check the {which} complexity. "
                "How much work happens per element, and what do you store?"
            )
    elif context.state == "FOLLOW_UP":
        message = "Thanks, that's all I had. Good work today."
        transition = "COMPLETE"
    else:
        message = "Thanks."
    return InterviewerTurn(
        message=message,
        recommended_transition=transition,
        learner_event_type=event_type,
        capability_tags=tags,
    )


def render_prompt(context: TurnContext) -> tuple[str, str, str]:
    """Return (system, user, prompt_id) for the LLM interviewer."""
    template = load_prompt("interviewer", PROMPT_VERSION)
    problem = context.problem.definition
    policy = context.policy
    transcript = "\n".join(
        f"[{actor}] {fence('learner_message', content, 1200) if actor == 'learner' else content}"
        for actor, content in context.transcript[-16:]
    )
    system = template.render(
        mode=policy.mode,
        policy_summary=(
            f"clarifications={policy.clarification_style}; "
            f"concept_explanations={'allowed' if policy.concept_explanations else 'no'}; "
            f"debug_help={'allowed' if policy.debug_help else 'no'}; "
            f"unsolicited_nudges={'allowed' if policy.unsolicited_nudges else 'no'}"
        ),
        state=context.state,
        state_guidance=STATE_GUIDANCE[context.state],
        hints_remaining=str(context.hints_remaining),
        allowed_transitions=", ".join(sorted(TRANSITIONS[context.state])) or "none",
        learner_event_types=", ".join(LEARNER_UTTERANCES),
        capability_slugs=", ".join(context.capability_slugs),
        problem_statement=problem.statement[:4000],
        clarifications="\n".join(
            f"- Q: {item.question} A: {item.answer}" for item in problem.clarifications
        ),
        follow_ups="\n".join(f"- {item}" for item in problem.follow_ups),
        weaknesses=", ".join(context.weaknesses) or "none recorded",
        execution_summary=context.execution_summary or "no runs yet",
        code=fence("candidate_code", context.code or "(empty)", 4000),
        transcript=transcript or "(no messages yet)",
    )
    if context.entering_state or context.learner_message is None:
        user = f"The interview just entered {context.state}. Say your next line."
    else:
        user = "The candidate just said:\n" + fence("learner_message", context.learner_message)
    return system, user, template.id


def llm_turn(
    provider: LLMProvider, context: TurnContext
) -> tuple[InterviewerTurn, LLMResult[InterviewerTurn], str]:
    system, user, prompt_id = render_prompt(context)
    result = provider.generate(system=system, user=user, schema=InterviewerTurn)
    return result.value, result, prompt_id
