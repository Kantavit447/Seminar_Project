"""หมายเลขหลักฐานเฉพาะข้อ พร้อมตำแหน่งข้อความเดิม โดยไม่ใช้โมเดลหรือย่อข้อความ."""
import re


def build_evidence_index(sources):
    index = {}
    prefixes = {'QUESTION': 'Q', 'DRAFT_ANALYSIS': 'DA', 'DRAFT_ANSWER': 'DR'}
    for source, text in sources.items():
        start, number = 0, 1
        while start < len(text):
            end = min(start + 600, len(text))
            if end < len(text):
                # Prefer existing line/space boundaries. Never cut a word just to meet 600.
                newline = text.rfind('\n', start, end)
                spaces = list(re.finditer(r'\s+', text[start:end]))
                if newline >= start:
                    end = newline + 1
                elif spaces and spaces[-1].end() >= 300:
                    end = start + spaces[-1].end()
                else:
                    following = re.search(r'\s+', text[end:])
                    end = end + following.end() if following else len(text)
            evidence_id = f'{prefixes.get(source, source)}-S{number}'
            index[evidence_id] = dict(source=source, start=start, end=end, text=text[start:end])
            start, number = end, number + 1
    return index


def render_evidence_source(index, source):
    return ''.join(f'\n[EVIDENCE {key}]\n{item["text"]}' for key, item in index.items()
                   if item['source'] == source)


def resolve_evidence(feedback, index):
    """ขยาย ID เป็นข้อความเดิมเพื่อรายงานเท่านั้น ไม่ใช้ตัดสินความหมายของ verdict."""
    return {check['axis']: [dict(evidence_id=key, source=index[key]['source'],
            start=index[key]['start'], end=index[key]['end'], quote=index[key]['text'])
            for key in check['evidence_ids']] for check in feedback['checks']}
