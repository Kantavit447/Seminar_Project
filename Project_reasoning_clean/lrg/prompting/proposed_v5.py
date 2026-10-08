"""แยกช่องหลักฐานตามแหล่งสำหรับ v5 โดยคงเกณฑ์ตัดสินเดิม."""
from typing import Literal, Union
from pydantic import ConfigDict, Field, create_model


def selected_ids(check):
    evidence = check["evidence_ids"]
    if isinstance(evidence, list):
        return evidence
    return [value for key, value in evidence.items() if key != "supporting_ids" and value is not None] + evidence.get("supporting_ids", [])


def build_v5_structure(ids, *, assess=False):
    config = ConfigDict(extra="forbid", strict=True)
    groups = {
        "question": [i for i in ids if i.startswith("Q-S")],
        "draft": [i for i in ids if i.startswith(("DA-S", "DR-S"))],
        "law": [i for i in ids if i.startswith("P")],
        "analysis": [i for i in ids if i.startswith("DA-S")],
        "answer": [i for i in ids if i.startswith("DR-S")],
    }
    required = {"I": ("question", "draft"), "R": ("law", "draft"),
                "A": ("question", "law", "draft"), "C": ("analysis", "answer")}
    if not all(groups.values()):
        raise ValueError("v5 requires question, draft and legal evidence catalogues.")
    assessment = create_model("ClaimAssessment", __config__=config,
        claim=(str, Field(min_length=1, max_length=120)),
        criterion=(str, Field(min_length=1, max_length=160)),
        comparison=(str, Field(min_length=1, max_length=240))) if assess else None
    models = []
    for axis, slots in required.items():
        for passing in (True, False):
            label = axis + ("Pass" if passing else "NonPass")
            fields = {}
            for slot in slots:
                kind = Literal.__getitem__(tuple(groups[slot]))
                fields[slot] = (kind if passing else kind | None, ...)
            # Non-PASS can cite any available source exposing an error or evidence gap.
            if not passing:
                kind = Literal.__getitem__(tuple(ids))
                fields["supporting_ids"] = (list[kind], Field(min_length=0, max_length=3))
            evidence = create_model(label + "Evidence", __config__=config, **fields)
            fields = dict(
                axis=(Literal.__getitem__((axis,)), ...),
                verdict=(Literal["PASS"] if passing else Literal["FAIL", "UNCERTAIN"], ...),
                reason=(str, Field(min_length=1, max_length=200)),
                evidence_ids=(evidence, ...),
                revision=(type(None) if passing else str | None, Field(...) if passing else Field(..., max_length=160)))
            if assess:
                fields = dict(axis=fields["axis"], assessment=(assessment, ...),
                    evidence_ids=fields["evidence_ids"], reason=fields["reason"],
                    verdict=fields["verdict"], revision=fields["revision"])
            models.append(create_model(label + "Check", __config__=config, **fields))
    return create_model("IRACVerification", __config__=config,
        checks=(list[Union.__getitem__(tuple(models))], Field(min_length=4, max_length=4)))
