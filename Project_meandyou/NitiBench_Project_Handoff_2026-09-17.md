# NitiBench Project Handoff / Current Research & Engineering State

Last updated: 2026-09-17

> Purpose of this file:
> This is a handoff document for continuing work on the user's main NitiBench / Thai Legal QA project.
> Treat this document as a conversation-derived project map, not as an absolute source of truth about the current repository.
> Before making code changes, inspect the actual repository and reconcile this handoff with the files that really exist.
> If this document conflicts with the repository, report the discrepancy first.

## 1. Main Research Goal

The project studies inference-time reasoning for Thai legal question answering using a small/general-purpose LLM without weight fine-tuning.

Main idea:
- Keep the model fixed.
- Keep the legal context fixed within each context condition.
- Change only the reasoning method.
- Measure whether more structured inference-time reasoning improves answer quality.

Primary model:
- Qwen2.5-7B
- served locally through Ollama / OpenAI-compatible endpoint

Primary dataset:
- NitiBench-Tax

The main contribution is reasoning, not retrieval.

## 2. Core Research Question

The central question is approximately:

> How do different inference-time reasoning methods affect the quality of Thai legal QA when using the same model and the same legal context?

Secondary questions:
1. Does a general reasoning cue (Zero-shot CoT) improve over Direct Prompting?
2. Does a legal-specific reasoning structure (IRAC) improve over general CoT?
3. Does structured verification + conditional correction improve over IRAC alone?
4. When performance is weak, is the bottleneck more related to retrieval or reasoning?
5. What inference-time cost is added by more complex reasoning methods?

## 3. Main Experimental Design

The main controlled experiment is:
- 2 Legal Context conditions
- 4 Reasoning Methods
- Total = 8 conditions

Context condition A: Retrieved Context
- All reasoning methods receive the same saved retrieved legal context for a given question.

Context condition B: Golden Context
- All reasoning methods receive the gold legal provisions associated with the question.

Reasoning methods:
1. Direct Prompting
2. Zero-shot Chain-of-Thought
3. IRAC
4. Proposed Method:
   - IRAC Generator
   - Structured Verifier
   - Conditional Corrector

| Context | Direct | Zero-shot CoT | IRAC | Proposed |
|---|---|---|---|---|
| Retrieved | Yes | Yes | Yes | Yes |
| Golden | Yes | Yes | Yes | Yes |

Important:
- Direct is not No-RAG.
- All four methods receive either Retrieved or Golden legal context.
- No-RAG is not part of the current main 8-condition design.

## 4. Main Model / Generation Controls

Target controlled settings:
- Model: Qwen2.5:7b
- Temperature: 0
- Seed: 42
- Max tokens: 4096
- Batch size: 1

The same evaluator and output schema should be used across all reasoning methods.

## 5. Dataset Split / Development Discipline

Primary dataset:
- NitiBench-Tax
- 50 total questions

Engineering/debug indices:
- 0000
- 0001
- 0002
- 0003
- 0008
- 0023
- 0026
- 0036
- 0041
- 0046

These 10 are used for:
- debugging
- schema validation
- prompt/interface engineering
- checking that the pipeline works

The remaining 40 questions are treated as held-out final evaluation items.

Important:
- Do not use held-out results to tune prompts before method freeze.
- Prompt/method policies should be frozen before running the final 40.

## 6. Main Pipeline Decision

The project has moved away from a simple custom baseline_runner.py as the main experimental pipeline.

The main direction is to use the NitiBench-style end-to-end pipeline, especially:
- script/response_e2e.py
- PromptManager
- Ragger
- augmenter/context formatting
- model wrapper / OpenAI-compatible interface

The goal is comparability and controlled experiments.

## 7. Retrieval State

Old / naive retrieval:
- Recall@10 = 0.077465
- MRR@10 = 0.123524

This is no longer the intended main Retrieved Context condition.

Current Retrieved Context:
- chunking/golden/nodes.json
- approximately 5,127 nodes
- human-finetuned BGE-M3 style retrieval setup
- top-10
- no-ref / no NitiLink for the current saved condition

Saved retrieval result is believed to be around:
results/current/retrieval_evaluation/section_based_no_ref/retrieval_results.json

Known approximate retrieval metrics:
- Recall@10 = 0.436620
- MRR@10 = 0.574524
- 38/50 had at least one gold provision retrieved

This retrieval should be reused as saved context rather than rerun separately for each reasoning method.

Reason:
> Retrieval is not the main contribution, so all reasoning methods should receive the same retrieved context for a question.

## 8. Golden Context State

Golden Context should not use the retriever.

Intended behavior:
1. Read relevant_laws for each question.
2. Resolve exact gold provision IDs against chunking/golden/nodes.json.
3. Build legal context from those exact gold provisions.
4. Do not expose gold answer, reference answer, evaluator score, or gold reasoning.

Known engineering result:
- 27 gold provisions across the 10 engineering questions
- exact resolved: 27/27
- unresolved: 0

Known case:
- source 0008 resolves to ประมวลรัษฎากร-65

## 9. Common Prompt Interface v3

A major engineering issue was citation formatting hallucination.

Earlier behavior included:
- putting section number inside the law name
- inventing subsection structures
- inconsistent JSON formatting
- malformed citation output

Therefore the project moved to citation-by-ID.

Legal context format example:

[PROVISION P1]
LAW_NAME: ...
SECTION_ID: ...
LAW_TEXT:
...
[/PROVISION P1]

Allowed IDs block:

[ALLOWED_CITATION_IDS]
P1, P2, P3
[/ALLOWED_CITATION_IDS]

Model-facing output:

{
  "analysis": "...",
  "answer": "...",
  "citation_ids": ["P1", "P3"]
}

Final evaluator-facing output:

{
  "analysis": "...",
  "answer": "...",
  "citations": [
    {
      "law": "...",
      "section": "..."
    }
  ]
}

Important:
- The mapper does not choose citations.
- The mapper does not correct semantic citation choice.
- The mapper does not use gold data.
- The mapper only converts selected P-IDs into deterministic law/section metadata.

This interface should be reused by Direct, CoT, IRAC, and Proposed.

## 10. Citation Enum / Schema Constraint

Desired behavior:
- citation_ids may be empty.
- If non-empty, every ID must be one of the actual P1...Pn IDs available for that question.
- No fuzzy normalization.
- Invalid IDs should be logged rather than silently fixed.

An audit tool believed to be involved:
tools/evaluation/audit_common_interface_v3_citation_id.py

Important distinction:
- schema_invalid = structural/schema failure
- invalid_provision_ids = invalid ID value / not in allowed set

## 11. Direct + Retrieved Status

Direct Prompting with Retrieved Context and citation-ID enum interface has already passed engineering on the 10 development items.

Known audit summary:
- total_answers = 10
- schema_invalid = 0
- empty_answers = 0
- questions_without_citation_ids = 0
- invalid_provision_ids = 0
- duplicate_provision_ids = 0
- mapping_failures = 0
- final_citation_not_in_context = 0
- law_includes_section = 0
- section_is_long_text = 0
- xml_copied = 0
- total_selected_ids = 39
- total_final_citations = 39
- mean citations/question = 3.9

Known selected citation counts:
- 0000 -> 10
- 0001 -> 1
- 0002 -> 1
- 0003 -> 7
- 0008 -> 1
- 0023 -> 1
- 0026 -> 2
- 0036 -> 10
- 0041 -> 3
- 0046 -> 3

Interpretation:
Some questions over-cite. This is currently considered semantic citation-selection behavior, not an interface bug. Citation precision should penalize it during evaluation.

## 12. Direct + Golden Status

Direct Prompting with Golden Context also passed the 10 engineering items.

Known audit summary:
- total_answers = 10
- schema_invalid = 0
- empty_answers = 0
- questions_without_citation_ids = 0
- invalid_provision_ids = 0
- duplicate_provision_ids = 0
- mapping_failures = 0
- final_citation_not_in_context = 0
- unresolved_gold_provisions = 0
- gold_context_empty = 0
- law_includes_section = 0
- section_is_long_text = 0
- xml_copied = 0
- total selected IDs = 22
- total final citations = 22
- mean citations/question = 2.2

Known gold provisions / selected IDs:
- 0000: 6 / 3
- 0001: 4 / 4
- 0002: 3 / 2
- 0003: 1 / 1
- 0008: 1 / 1
- 0023: 4 / 4
- 0026: 2 / 2
- 0036: 1 / 1
- 0041: 1 / 1
- 0046: 4 / 3

Interpretation:
Direct infrastructure should be treated as largely frozen unless repository inspection reveals a real bug.

## 13. Known / Likely Relevant Files

Please verify these against the actual repository before editing.

Likely relevant files:
- lrg/prompting/prompt_manager.py
- lrg/augmenter/augmenter.py
- lrg/e2e/ragger.py
- script/response_e2e.py
- prompt templates / schema definitions for common interface v3
- tools/evaluation/audit_common_interface_v3_citation_id.py

Known/expected Direct configs:
- config/local/response/section_based_rag_qwen_direct_v3_citation_id_enum_engineering_10.yaml
- config/local/response/golden_qwen_direct_v3_citation_id_enum_engineering_10.yaml

Known/expected outputs:
- results/current/common_interface_v3/section_based_direct_citation_id_enum_engineering_10/.../tax_response.json
- results/current/common_interface_v3/golden_direct_citation_id_enum_engineering_10/.../tax_response.json

These paths must be verified against the real filesystem.

## 14. Reasoning Method Definitions

### Direct Prompting
- control condition
- no explicit reasoning scaffold
- still receives legal context
- still uses citation-ID interface
- not No-RAG

### Zero-shot Chain-of-Thought

Academic basis:
- Kojima et al., 2022, “Large Language Models are Zero-Shot Reasoners”

Design intent:
- add only a general reasoning cue
- no examples
- no IRAC labels
- no legal-specific workflow
- no verifier

Thai cue previously proposed:
“พิจารณาคำถามและบทกฎหมายที่ให้มาอย่างเป็นลำดับขั้น แล้วจึงสรุปคำตอบ”

Do not turn Zero-shot CoT into:
- Issue -> Rule -> Application -> Conclusion
- fact extraction workflow
- legal checklist
- verifier

### IRAC
Legal reasoning scaffold:
- Issue
- Rule
- Application
- Conclusion

Purpose:
- compare general reasoning scaffold vs legal-domain-specific structure

Should use:
- one LLM call
- same context
- same model
- same output/citation interface

### Proposed Method

Current latest design:
IRAC-based Generation + IRAC-grounded Structured Verification + Conditional Correction

Workflow:

Question + Legal Context
        |
        v
IRAC Generator
        |
        v
IRAC Draft
        |
        v
Structured Verifier
        |
        +-- I: Issue Alignment
        +-- R: Rule Grounding
        +-- A: Application Consistency
        +-- C: Conclusion Consistency
        |
        v
All PASS?
   |       |
  YES      NO
   |        |
   |        v
   |     Corrector
   |        |
   +--------+
        |
        v
Final Answer

Important:
- Maximum one correction.
- Do not loop verifier/corrector until PASS.
- Same Qwen2.5-7B is intended for Generator, Verifier, and Corrector.
- Roles differ by prompt.

## 15. Structured Verifier: Latest Agreed Scope

The verifier is not intended to act as an expert Thai lawyer.

It should not independently judge:
“Is this legally correct in the real world?”

Instead it should check consistency and grounding based only on:
- Question
- Provided Legal Context
- IRAC Draft

Four checks:

### I. Issue Alignment
Does the Issue accurately identify and cover what the legal question asks?
Comparison: Question <-> Issue

### R. Rule Grounding
Are the material legal rules stated in the draft supported by the provided legal context, without omitting or altering required conditions?
Comparison: Legal Context <-> Rule

### A. Application Consistency
Does the Application apply the supported Rule to the facts in the Question consistently, without skipping required conditions or inventing unsupported facts?
Comparison: Question Facts + Rule <-> Application

### C. Conclusion Consistency
Does the Conclusion logically follow from the Application and answer the identified Issue?
Comparison: Issue + Application <-> Conclusion

## 16. Verifier Rationale

Academic framing:
- IRAC provides the structural relationship among Issue, Rule, Application, Conclusion.
- Verification/correction literature motivates checking intermediate reasoning before finalizing.
- LegalReasoner can be cited as inspiration for step-wise verification/correction.
- This project does not reproduce LegalReasoner’s fine-tuned verifier or expert-designed correction pipeline.
- The project instead proposes prompt-based structured self-verification grounded in IRAC and the provided context.

Important limitation:
The same model may fail to detect its own mistakes.

Therefore:
- verifier decisions are not ground truth
- pre-correction and post-correction outputs should be preserved
- final evaluation determines whether correction helped or hurt

## 17. Proposed Method: Calls

If verifier passes:
- Generator = 1 call
- Verifier = 1 call
- Total = 2

If verifier fails:
- Generator = 1
- Verifier = 1
- Corrector = 1
- Total = 3

No repeated loop.

## 18. Leakage Rules

Verifier/Corrector must never see:
- reference answer
- gold answer
- gold reasoning
- evaluator score
- gold citation labels beyond the legal context condition itself

For Golden Context:
- legal provisions are gold legal context
- answer/reasoning remains hidden

For Retrieved Context:
- verifier/corrector cannot retrieve new law
- use the same retrieved context given to the generator

Correction must not trigger new retrieval in the current design.

## 19. Current Evaluation Direction

Research focus is reasoning quality, not retrieval research.

Main answer quality:
- Coverage
- Contradiction

Citation quality:
- Citation Precision
- Citation Recall
- Citation F1

Secondary inference cost:
- LLM calls
- total tokens
- latency

Proposed-specific analysis:
- verifier PASS/FAIL rate
- correction rate
- pre-correction output
- post-correction output
- whether corrected outputs improve / remain unchanged / degrade

Retrieval metrics:
- do not make them the main reasoning comparison
- existing retrieval metrics may be reported as setup/context quality only

## 20. Research Comparison Logic

Direct vs Zero-shot CoT:
- effect of adding a general intermediate-reasoning cue

Zero-shot CoT vs IRAC:
- legal-specific structure vs general reasoning

IRAC vs Proposed:
- incremental effect of structured verification + conditional correction

Retrieved vs Golden:
- retrieval bottleneck vs reasoning bottleneck

## 21. External OpenThai 2.0 Legal Comparison

There is a separate project for OpenThai 2.0 Legal.

Do not merge that code into this repository unless explicitly requested.

Purpose:
- external practical reference
- not part of the 8 controlled conditions
- not a baseline for isolating reasoning-method effects

Conceptually:

Main controlled experiment:
Qwen2.5-7B x 4 reasoning methods x 2 contexts

Then external comparison:
Qwen2.5-7B + Proposed
vs
OpenThai 2.0 Legal

Keep this separate from the causal reasoning-method comparison.

## 22. Current Implementation Roadmap

Intended next order:

1. Inspect repository and reconcile this handoff with actual files.
2. Treat Direct Retrieved + Direct Golden as frozen unless a real bug is found.
3. Implement / verify Zero-shot CoT:
   - Retrieved
   - Golden
4. Run engineering 10 and audit.
5. Freeze CoT if interface/reliability passes.
6. Implement IRAC:
   - Retrieved
   - Golden
7. Run engineering 10 and audit.
8. Freeze IRAC.
9. Implement Proposed:
   - Retrieved
   - Golden
   - generator
   - structured verifier
   - conditional corrector
   - stage logging
10. Run engineering 10 and audit.
11. Freeze all prompts and policies.
12. Run held-out final 40.
13. Evaluate.
14. Analyze final results.

## 23. Zero-shot CoT Expected Next Design

Zero-shot CoT should reuse the Direct pipeline as much as possible.

Only the reasoning instruction should change.

Do not change:
- model
- retrieval
- legal context
- citation interface
- deterministic citation mapping
- evaluator-facing schema

Suggested reasoning method identifier:
zero_shot_cot

Expected config naming discussed previously:

Retrieved:
- section_based_rag_qwen_cot_v3_citation_id_enum_diagnostic_source_0008.yaml
- section_based_rag_qwen_cot_v3_citation_id_enum_engineering_10.yaml

Golden:
- golden_qwen_cot_v3_citation_id_enum_diagnostic_source_0008.yaml
- golden_qwen_cot_v3_citation_id_enum_engineering_10.yaml

Possible output roots discussed:
- results/current/common_interface_v3/diagnostics/retrieved_cot_v3_citation_id_enum_source_0008/
- results/current/common_interface_v3/retrieved_cot_citation_id_enum_engineering_10/
- results/current/common_interface_v3/diagnostics/golden_cot_v3_citation_id_enum_source_0008/
- results/current/common_interface_v3/golden_cot_citation_id_enum_engineering_10/

These names are conversation-derived and MUST be verified against current repository conventions.

## 24. Suggested Run Order Per Context

For a newly implemented reasoning method:
1. Dump/inspect prompt
2. Run diagnostic source 0008
3. Audit diagnostic
4. Run engineering 10
5. Audit engineering 10
6. Only freeze if interface and reliability are clean

Do not jump directly to held-out 40.

## 25. Important Engineering Principles

Reuse before duplication.

Do not fork the entire pipeline for every method.

Prefer:
- shared context construction
- shared citation interface
- shared output mapping
- method-specific reasoning prompt/scaffold

Do not change multiple variables at once.

When adding CoT:
- change only CoT reasoning cue

When adding IRAC:
- change only reasoning scaffold

When adding Proposed:
- add verifier/corrector stages on top of IRAC

Do not optimize semantically against the engineering 10.

## 26. Current Known Uncertainties / Things Codex Must Verify

Before modifying code, verify:

1. Does the current repository actually contain all Direct configs listed above?
2. Are the Direct Retrieved and Direct Golden outputs still present?
3. Does the current audit script match the described citation-ID enum behavior?
4. Is Zero-shot CoT already partially implemented from a prior session?
5. Are there prompt templates already created for CoT?
6. Are any IRAC/Proposed files already present?
7. What is the exact current model config / YAML format?
8. What is the exact output path convention currently used?
9. Is the saved retrieval path exactly as described?
10. Is Golden Context implemented inside response_e2e.py, ragger.py, or elsewhere?
11. Are any uncommitted changes present?
12. Are there stale/duplicate configs from earlier iterations?

Do not assume this handoff is perfectly synchronized with the filesystem.

## 27. What Codex Should NOT Do During Initial Audit

During the first continuation step:
- do not modify files
- do not rerun model inference
- do not rerun retrieval
- do not run held-out 40
- do not change Direct prompts
- do not implement IRAC/Proposed yet
- do not delete old outputs
- do not restructure the project

First inspect and report.

## 28. Desired Initial Codex Audit Report

After inspecting the repository, report:

### A. Repository state
- current branch
- git status
- important uncommitted changes
- relevant directories/files

### B. Pipeline map
Explain the actual call flow:
config -> response_e2e.py -> prompt/context creation -> model wrapper -> output parsing -> citation mapping -> result saving

Use actual filenames/functions.

### C. Direct Retrieved
- config
- prompt mode
- output
- audit result
- whether it matches this handoff

### D. Direct Golden
Same items.

### E. Citation interface
Explain actual implementation of:
- P1...Pn assignment
- allowed IDs
- schema constraint
- deterministic mapping
- audit

### F. Retrieval / Golden adapters
Explain how each context is built in current code.

### G. Existing CoT work
Find any:
- config
- template
- method switch
- result
- partial implementation

State exactly what exists and what is missing.

### H. Existing IRAC / Proposed work
Same.

### I. Discrepancies
List anything in this handoff that does not match the repo.

### J. Recommended next smallest step
Prefer:
finish/verify Zero-shot CoT Retrieved + Golden on engineering 10

unless the repository reveals that this is already complete.

## 29. Stop Gate

After the initial audit:
STOP.

Do not edit code until the user confirms the audit and next step.

## 30. Short State Summary

At the conversation level, intended state is:

Infrastructure / context
- NitiBench E2E pipeline direction: done
- Retrieved context prepared: done
- Golden context adapter prepared: done
- Citation-ID enum interface: done
- deterministic citation mapping: done

Reasoning methods
- Direct Retrieved engineering: done
- Direct Golden engineering: done
- Zero-shot CoT implementation: must be verified
- IRAC: not intended as complete
- Proposed: not intended as complete

Next expected work
- audit actual repo
- reconcile state
- Zero-shot CoT
- IRAC
- Proposed
- freeze
- final 40
- evaluation

## 31. Final Instruction to Future Coding Agent

Do not treat the project as a blank slate.

Preserve the controlled comparison:

> same model + same context + same output interface, change only reasoning method.

The code architecture should make that experimental logic obvious and reproducible.
