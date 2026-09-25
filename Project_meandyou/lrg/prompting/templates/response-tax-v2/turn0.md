<user> Take a deep breath and think carefully.

You are given a Thai tax law question under <ข้อหารือ></ข้อหารือ>.
Relevant law provisions may be provided under <ข้อกฎหมาย></ข้อกฎหมาย>.

Each provided law uses one of these formats:

<law section="SECTION" law_name="LAW_NAME">...</law>

or

<related_law section="SECTION" law_name="LAW_NAME" parent_section="PARENT_SECTION" parent_law_name="PARENT_LAW_NAME">...</related_law>

Analyse the case using only the provided case details and laws.

You must return exactly one valid JSON object containing exactly these keys:
"analysis", "answer", and "citations".

Rules for "analysis":
- Write the legal analysis in English.
- Use only facts and laws provided in the prompt.
- Do not invent facts or laws.

Rules for "answer":
- Write the final answer in Thai only.
- Answer every material part of the question.
- Keep the answer direct and complete.

Rules for "citations":
- Return a JSON array.
- Cite only laws that directly support the answer.
- Every citation must come from a provided <law> or <related_law> tag.
- Do not cite a law merely because it appears in the context.
- If you are not certain that a citation exactly matches a provided tag, return an empty citations list: [].

For every citation object:

1. "law" must contain only the exact value of the law_name attribute.
2. "law" must not contain the word "มาตรา".
3. "law" must not contain a section number.
4. "law" must not contain XML tags or law text.
5. "section" must contain only the exact value of the section attribute.
6. "section" must not contain the law name.
7. "section" must not contain the word "มาตรา".
8. "section" must not contain XML tags or explanatory text.
9. Do not copy the law body, legal prose, or any long text into either field.
10. Never combine a law name and a section identifier in one field.

Correct citation:

{"law": "ประมวลรัษฎากร", "section": "80/1"}

Incorrect citations:

{"law": "ประมวลรัษฎากร มาตรา 80/1", "section": "80/1"}

{"law": "<law section=\"80/1\" law_name=\"ประมวลรัษฎากร\">", "section": "80/1"}

{"law": "ประมวลรัษฎากร", "section": "มาตรา 80/1 แห่งประมวลรัษฎากร"}

{"law": "ประมวลรัษฎากร มาตรา 80/1", "section": "80/1"}

{"law": "ประมวลรัษฎากร", "section": "ข้อความกฎหมายยาวที่คัดลอกมาจากบริบท"}

When no exact supporting citation can be identified, this is correct:

{"analysis": "English legal analysis", "answer": "คำตอบภาษาไทย", "citations": []}

Your final output must follow this structure:

{
  "analysis": "English legal analysis",
  "answer": "คำตอบภาษาไทย",
  "citations": [
    {
      "law": "ประมวลรัษฎากร",
      "section": "80/1"
    }
  ]
}

Return JSON only.
Do not include Markdown code fences.
Do not include any text before or after the JSON.

<assistant> I will strictly follow the required JSON structure and citation rules.
