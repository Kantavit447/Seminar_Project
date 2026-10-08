"""สร้าง prompt และตรวจ feedback ของ Proposed โดยไม่เรียกโมเดลหรือเลือก context ใหม่."""

import json
from pathlib import Path
from typing import Literal
from types import SimpleNamespace

from .proposed_v5 import build_v5_structure, selected_ids
from .proposed_evidence import build_evidence_index, render_evidence_source

from pydantic import ConfigDict, Field, create_model

from .prompt_manager import PromptManager
from ..augmenter import NitiLinkAugmenter
from ..e2e.ragger import Ragger


AXES = ["I", "R", "A", "C"]
TEMPLATES = Path(__file__).with_name("templates")


VERSIONS = ("proposed-tax-v1", "proposed-tax-v2", "proposed-tax-v3", "proposed-tax-v4", "proposed-tax-v5", "proposed-tax-v6")


def check_version(version):
    if version not in VERSIONS:
        raise ValueError(f"Unsupported Proposed prompt version: {version}")


def build_verifier_structure(allowed_ids, version="proposed-tax-v1", evidence_ids=None):
    """Schema จำกัดแหล่งอ้างอิงตามข้อ; กติกาข้ามฟิลด์/ข้อความตรวจเพิ่มก่อนใช้ feedback."""
    check_version(version)
    if len(allowed_ids) != len(set(allowed_ids)) or any(
        pid != f"P{rank}" for rank, pid in enumerate(allowed_ids, start=1)
    ):
        raise ValueError("Expected unique rank-ordered P-IDs from the existing provision map.")
    config = ConfigDict(extra="forbid", strict=True)
    source_type = Literal.__getitem__(tuple(["QUESTION", "DRAFT_ANALYSIS", "DRAFT_ANSWER"] + allowed_ids))
    evidence = create_model("VerificationEvidence", __config__=config,
        source=(source_type, ...), quote=(str, ...))
    if version in ("proposed-tax-v4", "proposed-tax-v5", "proposed-tax-v6"):
        if not evidence_ids or len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("v4 needs a unique, nonempty evidence catalogue.")
        if version in ("proposed-tax-v5", "proposed-tax-v6"):
            return build_v5_structure(evidence_ids, assess=version == "proposed-tax-v6")
        evidence_type = Literal.__getitem__(tuple(evidence_ids))
        check = create_model("VerificationCheck", __config__=config,
            axis=(Literal["I", "R", "A", "C"], ...),
            verdict=(Literal["PASS", "FAIL", "UNCERTAIN"], ...),
            reason=(str, Field(min_length=1, max_length=200)),
            evidence_ids=(list[evidence_type], Field(min_length=1, max_length=3)),
            revision=(str | None, Field(..., max_length=160)))
        return create_model("IRACVerification", __config__=config,
            checks=(list[check], Field(min_length=4, max_length=4)))
    if version == "proposed-tax-v3":
        evidence = create_model("VerificationEvidence", __config__=config,
            source=(source_type, ...), quote=(str, Field(min_length=1, max_length=80)))
        check = create_model("VerificationCheck", __config__=config,
            axis=(Literal["I", "R", "A", "C"], ...),
            verdict=(Literal["PASS", "FAIL", "UNCERTAIN"], ...),
            reason=(str, Field(min_length=1, max_length=200)),
            evidence=(list[evidence], Field(min_length=1, max_length=3)),
            revision=(str | None, Field(..., max_length=160)))
        return create_model("IRACVerification", __config__=config,
            checks=(list[check], Field(min_length=4, max_length=4)))
    issue = create_model("VerificationIssue", __config__=config,
        draft_field=(Literal["analysis", "answer"], ...),
        draft_quote=(str | None, ...), problem=(str, ...),
        evidence=(list[evidence], Field(min_length=1)), revision=(str, ...))
    extra = {"evidence": (list[evidence], Field(min_length=1))} if version == "proposed-tax-v2" else {}
    check = create_model("VerificationCheck", __config__=config,
        axis=(Literal["I", "R", "A", "C"], ...),
        verdict=(Literal["PASS", "FAIL", "UNCERTAIN"], ...),
        reason=(str, ...), issues=(list[issue], ...), **extra)
    return create_model("IRACVerification", __config__=config,
        checks=(list[check], Field(min_length=4, max_length=4)))


def _prepare(question, nodes, draft):
    if not isinstance(question, str) or not question.strip():
        raise ValueError("A nonempty question is required.")
    nodes = list(nodes)
    provision_map = Ragger.build_provision_map(nodes)
    allowed = [item["provision_id"] for item in provision_map]
    answer_structure = PromptManager.build_citation_id_enum_structure(allowed)
    draft = answer_structure.model_validate(draft, strict=True).model_dump()
    if not draft["analysis"].strip() or not draft["answer"].strip():
        raise ValueError("A complete, nonempty IRAC draft is required.")
    sources = {"QUESTION": question, "DRAFT_ANALYSIS": draft["analysis"],
               "DRAFT_ANSWER": draft["answer"]}
    for item, node in zip(provision_map, nodes):
        raw_node = node.node if hasattr(node, "node") else node
        sources[item["provision_id"]] = raw_node.text
    context = NitiLinkAugmenter.serialize_common_v3(
        nodes, include_provision_id=True, provision_id_only_blocks=True)
    query = f"{context}\n[QUESTION]\n{question}\n[/QUESTION]"
    return query, draft, allowed, sources, answer_structure


def _validate_feedback(feedback, draft, allowed, sources, version="proposed-tax-v1"):
    index = build_evidence_index(sources) if version in ("proposed-tax-v4", "proposed-tax-v5", "proposed-tax-v6") else None
    feedback = build_verifier_structure(allowed, version, list(index) if index else None).model_validate(feedback, strict=True).model_dump()
    if [check["axis"] for check in feedback["checks"]] != AXES:
        raise ValueError("Feedback must contain I, R, A, C exactly once, in order.")
    for check in feedback["checks"]:
        if version == "proposed-tax-v6" and any(not text.strip() for text in check["assessment"].values()):
            raise ValueError("Each assessment field needs nonempty text.")
        if not check["reason"].strip():
            raise ValueError("Each check needs a nonempty reason.")
        if version in ("proposed-tax-v3", "proposed-tax-v4", "proposed-tax-v5", "proposed-tax-v6"):
            revision = check["revision"]
            if check["verdict"] == "FAIL":
                if not isinstance(revision, str) or not revision.strip():
                    raise ValueError("FAIL requires a nonempty revision.")
            elif revision is not None:
                raise ValueError("PASS and UNCERTAIN require revision=null.")
        elif (check["verdict"] == "FAIL") != bool(check["issues"]):
            raise ValueError("Only FAIL may have issues, and FAIL needs at least one issue.")
        if version in ("proposed-tax-v2", "proposed-tax-v3", "proposed-tax-v4", "proposed-tax-v5", "proposed-tax-v6"):
            if version in ("proposed-tax-v4", "proposed-tax-v5", "proposed-tax-v6"):
                ids = selected_ids(check)
                if not 1 <= len(ids) <= 3:
                    raise ValueError("Each check needs 1-3 evidence IDs.")
                if len(ids) != len(set(ids)):
                    raise ValueError("Duplicate evidence IDs within a check.")
                cited = {index[key]["source"] for key in ids}
            else:
                for evidence in check["evidence"]:
                    quote = evidence["quote"]
                    if not quote.strip() or quote not in sources[evidence["source"]]:
                        raise ValueError("Check evidence quote must match its declared source exactly.")
                cited = {e["source"] for e in check["evidence"]}
            if check["verdict"] == "PASS":
                has_draft = bool(cited & {"DRAFT_ANALYSIS", "DRAFT_ANSWER"})
                has_law = bool(cited & set(allowed))
                required = {
                    "I": "QUESTION" in cited and has_draft,
                    "R": has_law and has_draft,
                    "A": "QUESTION" in cited and has_law and has_draft,
                    "C": {"DRAFT_ANALYSIS", "DRAFT_ANSWER"} <= cited,
                }
                if not required[check["axis"]]:
                    raise ValueError(f"PASS {check['axis']} lacks required evidence sources.")
        for issue in check.get("issues", []):
            if not issue["problem"].strip() or not issue["revision"].strip():
                raise ValueError("An issue needs a specific problem and revision.")
            quote = issue["draft_quote"]
            if quote is not None and (not quote.strip() or quote not in draft[issue["draft_field"]]):
                raise ValueError("draft_quote must match the selected draft field exactly.")
            for evidence in issue["evidence"]:
                quote = evidence["quote"]
                if not quote.strip() or quote not in sources[evidence["source"]]:
                    raise ValueError("Evidence quote must match its declared source exactly.")
    return feedback


def validate_verifier_feedback(feedback, *, question, nodes, draft, version="proposed-tax-v1"):
    """ตรวจรูปแบบและข้อความอ้างอิงเท่านั้น ไม่รับรองความถูกต้องทางกฎหมายของ verdict."""
    _, draft, allowed, sources, _ = _prepare(question, nodes, draft)
    return _validate_feedback(feedback, draft, allowed, sources, version)


def build_proposed_prompt(stage, *, question, nodes, draft, feedback=None, template_dir=None, version="proposed-tax-v1"):
    """คืน (formatted_prompt, Pydantic schema); รับเฉพาะข้อมูลที่อนุญาต ไม่มี LLM client.

    ผู้เรียกต้องตรวจ source/context/provenance และงบ input ก่อนนำไปเรียกโมเดลจริง
    การเก็บสถานะ การ fallback และการ resume เป็นหน้าที่ของ runner
    """
    check_version(version)
    if stage not in ("verifier", "corrector"):
        raise ValueError("stage must be verifier or corrector.")
    nodes = list(nodes)
    query, draft, allowed, sources, answer_structure = _prepare(question, nodes, draft)
    templates = Path(template_dir) if template_dir is not None else TEMPLATES
    instruction = (templates / (version if stage == "verifier" or version in ("proposed-tax-v4", "proposed-tax-v5", "proposed-tax-v6") else "proposed-tax-v1") / f"{stage}.md").read_text(encoding="utf-8").strip()
    data = query + "\n\n[DRAFT_JSON]\n" + json.dumps(draft, ensure_ascii=False, indent=2) + "\n[/DRAFT_JSON]"
    index = None
    if version in ("proposed-tax-v4", "proposed-tax-v5", "proposed-tax-v6"):
        index = build_evidence_index(sources)
        annotated = [SimpleNamespace(id_=node.id_, text=render_evidence_source(index, pid))
                     for node, pid in zip(nodes, allowed)]
        context = NitiLinkAugmenter.serialize_common_v3(annotated,
            include_provision_id=True, provision_id_only_blocks=True)
        parts = [context]
        for source in ("QUESTION", "DRAFT_ANALYSIS", "DRAFT_ANSWER"):
            parts.append(f"[{source}]" + render_evidence_source(index, source) + f"\n[/{source}]")
        parts.append("[DRAFT_CITATION_IDS]\n" + json.dumps(draft["citation_ids"]) + "\n[/DRAFT_CITATION_IDS]")
        data = "\n\n".join(parts)
    if stage == "verifier":
        if feedback is not None:
            raise ValueError("Verifier input must not contain feedback.")
        structure = build_verifier_structure(allowed, version, list(index) if index else None)
    else:
        feedback = _validate_feedback(feedback, draft, allowed, sources, version)
        if not any(check["verdict"] == "FAIL" for check in feedback["checks"]):
            raise ValueError("Correction requires validated feedback with at least one FAIL.")
        shared = (templates / "system_prompt_tax_v3_citation_id_enum.md").read_text(encoding="utf-8").strip()
        instruction = shared + "\n\n" + instruction
        data += "\n\n[FEEDBACK_JSON]\n" + json.dumps(feedback, ensure_ascii=False, indent=2) + "\n[/FEEDBACK_JSON]"
        structure = answer_structure
    return {"messages": [{"role": "system", "content": instruction},
                         {"role": "user", "content": data}]}, structure
