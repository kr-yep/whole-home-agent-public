"""Answer a yes/no location question from an already-resolved location answer.

Verification asks nothing new of the ledger. It compares one proposed place
against the relation path the projection already produced, so the same evidence
and the same abstentions govern it: an unresolved subject stays unresolved, and
a place this replay never recorded is reported as such rather than guessed at.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

VERIFICATION_SCHEMA = "whole-home-agent.location-verification.v1"

YES = "YES"
NO = "NO"
UNRESOLVED = "UNRESOLVED"
TARGET_UNKNOWN = "TARGET_UNKNOWN"

# Duplicated from the presentation module on purpose: that module is pinned by
# recorded milestone evidence, and three display names are not worth changing a
# frozen artifact over.
_DISPLAY_NAMES = {"bag": "包包", "key": "鑰匙", "sofa": "沙發"}
_PREDICATE_PHRASE = {"inside": "在{place}裡", "at_zone": "位於{place}"}


def _name(identifier: str | None) -> str:
    if identifier is None:
        return "那個位置"
    return _DISPLAY_NAMES.get(identifier, identifier)


@dataclass(frozen=True, slots=True)
class VerificationResult:
    verdict: str
    subject_id: str
    target_id: str | None
    location_id: str | None
    text: str

    def as_dict(self) -> dict[str, object]:
        return {
            "schema": VERIFICATION_SCHEMA,
            "verdict": self.verdict,
            "subject_id": self.subject_id,
            "target_id": self.target_id,
            "location_id": self.location_id,
            "text": self.text,
        }


def _where_clause(answer: Mapping[str, object]) -> str:
    """Describe the subject's own position, container included when there is one."""

    subject = _name(str(answer["subject_id"]))
    location = _name(str(answer["location_id"]))
    steps = answer.get("relation_path") or []
    for step in steps:
        if step["subject_id"] == answer["subject_id"] and step["predicate"] == "inside":
            container = _name(step["object_id"])
            return f"{subject}在{container}裡，而{container}位於{location}"
    return f"{subject}位於{location}"


def verify(
    answer: Mapping[str, object], target_id: str | None
) -> VerificationResult:
    """Compare a proposed place against one resolved location answer."""

    subject_id = str(answer["subject_id"])
    subject = _name(subject_id)
    status = str(answer["status"])

    if status != "FOUND":
        return VerificationResult(
            verdict=UNRESOLVED,
            subject_id=subject_id,
            target_id=target_id,
            location_id=None,
            text=(
                f"沒辦法判斷。在這段固定重播中，沒有有效證據可以定位{subject}；"
                f"系統回傳 {status}，不補猜位置。"
            ),
        )

    location_id = str(answer["location_id"])
    where = _where_clause(answer)

    if target_id is None:
        return VerificationResult(
            verdict=TARGET_UNKNOWN,
            subject_id=subject_id,
            target_id=None,
            location_id=location_id,
            text=(
                f"我的記錄裡沒有你說的那個位置，所以沒辦法回答是或不是。"
                f"不過在這段固定重播中，{where}。"
            ),
        )

    # The proposed place counts either as the resolved zone or as any container
    # along the chain: a key inside a bag that sits at the sofa is at both.
    on_chain = any(
        step["object_id"] == target_id for step in answer.get("relation_path") or []
    )
    if target_id == location_id or on_chain:
        # The chain sentence already names every place involved, so stating the
        # matched one again only repeats itself.
        return VerificationResult(
            verdict=YES,
            subject_id=subject_id,
            target_id=target_id,
            location_id=location_id,
            text=f"是的。在這段固定重播中，{where}。",
        )

    return VerificationResult(
        verdict=NO,
        subject_id=subject_id,
        target_id=target_id,
        location_id=location_id,
        text=(
            f"不是。在這段固定重播中，{where}，"
            f"沒有證據顯示{subject}在{_name(target_id)}。"
        ),
    )
