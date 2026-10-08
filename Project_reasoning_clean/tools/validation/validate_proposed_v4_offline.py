"""ตรวจ evidence-ID v4, ข้อความครบ, การดึงหลักฐานและ runner โดยไม่เรียก LLM/network."""
import asyncio
from copy import deepcopy
import json
from pathlib import Path
import socket
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
loop = asyncio.new_event_loop()
def forbidden(*args, **kwargs):
    raise AssertionError('Real network/LLM forbidden')
socket.socket.connect = socket.socket.connect_ex = socket.create_connection = forbidden
import yaml
import openai
openai.OpenAI = openai.AsyncOpenAI = forbidden
import lrg.llm
from script import response_proposed as runner
from lrg.prompting.proposed import build_proposed_prompt, validate_verifier_feedback, _prepare
from lrg.prompting.proposed_evidence import build_evidence_index, resolve_evidence

VERSION = 'proposed-tax-v4'
def fixture(verdict='PASS'):
    needed = {'I': ['Q-S1', 'DR-S1'], 'R': ['P1-S1', 'DA-S1'],
        'A': ['Q-S1', 'P1-S1', 'DA-S1'], 'C': ['DA-S1', 'DR-S1']}
    result = {'checks': [dict(axis=a, verdict='PASS', reason='Synthetic interface test only.',
        evidence_ids=needed[a], revision=None) for a in 'IRAC']}
    result['checks'][2]['verdict'] = verdict
    if verdict == 'FAIL': result['checks'][2]['revision'] = 'Synthetic correction.'
    return result

def assert_lossless(index, sources):
    for source, original in sources.items():
        pieces = [item for item in index.values() if item['source'] == source]
        assert ''.join(piece['text'] for piece in pieces) == original
        cursor = 0
        for piece in pieces:
            assert piece['start'] == cursor
            assert piece['text'] == original[piece['start']:piece['end']]
            cursor = piece['end']
        assert cursor == len(original)

async def main():
    rejected, cases, budgets = 0, [], []
    for text in ('กฎหมายไทย'*200, 'a'*601, '\n  hello\r\nworld  ', '', ' ' * 800):
        index = build_evidence_index({'QUESTION': text})
        assert_lossless(index, {'QUESTION': text})
    for context in ('golden', 'retrieved'):
        settings = yaml.safe_load((ROOT/f'config/local/response/proposed_{context}_v4_engineering_10.yaml').read_text(encoding='utf-8'))
        loaded = runner.load_inputs(settings)
        _, _, model, rows, _ = loaded
        budget = runner.Budget(runner.tokenizer_file(), runner.CONTEXT_WINDOWS[model])
        for row in rows:
            if row['draft'] is None: continue
            inputs = {key: row[key] for key in ('question', 'nodes', 'draft')}
            sources = _prepare(**inputs)[3]
            index = row['evidence_index']
            assert index == build_evidence_index(sources)
            assert_lossless(index, sources)
            for verdict in ('PASS', 'FAIL', 'UNCERTAIN'):
                feedback = validate_verifier_feedback(fixture(verdict), **inputs, version=VERSION)
                resolved = resolve_evidence(feedback, index)
                for entries in resolved.values():
                    for entry in entries:
                        assert entry['quote'] == sources[entry['source']][entry['start']:entry['end']]
            for mutation in ('unknown', 'duplicate', 'source', 'quote', 'pass_revision', 'fail_null', 'missing_axis'):
                bad = fixture()
                check = bad['checks'][0]
                if mutation == 'unknown': check['evidence_ids'][0] = 'Q-S99999'
                if mutation == 'duplicate': check['evidence_ids'] = ['Q-S1', 'Q-S1']
                if mutation == 'source': check['evidence_ids'] = ['Q-S1']
                if mutation == 'quote': check['quote'] = 'Not an allowed field'
                if mutation == 'pass_revision': check['revision'] = 'Not allowed for PASS'
                if mutation == 'fail_null': check['verdict'] = 'FAIL'
                if mutation == 'missing_axis': bad['checks'].pop()
                try: validate_verifier_feedback(bad, **inputs, version=VERSION)
                except ValueError: rejected += 1
                else: raise AssertionError(mutation)
            sizes = {}
            for stage in ('verifier', 'corrector'):
                extra = {} if stage == 'verifier' else {'feedback': fixture('FAIL')}
                prompt, schema = build_proposed_prompt(stage, **inputs, version=VERSION, **extra)
                for key, item in index.items():
                    assert f'[EVIDENCE {key}]\n{item["text"]}' in prompt['messages'][1]['content']
                sizes[stage] = budget.check(prompt, schema, settings[f'{stage}_max_tokens'])['required']
            budgets.append(dict(context=context, source_idx=row['source_idx'], evidence_count=len(index), **sizes))

        actual_load = runner.load_inputs
        runner.load_inputs = lambda settings: loaded
        row, calls, mode = rows[0], [], 'PASS'
        class Fake:
            def __init__(self, config): self.config = config
            async def complete(self, **kwargs):
                stage = 'verifier' if kwargs['structure'].__name__ == 'IRACVerification' else 'corrector'
                calls.append((stage, self.config['max_tokens']))
                value = fixture(mode if mode != 'INVALID' else 'PASS') if stage == 'verifier' else deepcopy(row['draft'])
                if mode == 'INVALID': value['checks'][0]['evidence_ids'] = ['Q-S99999']
                return dict(content=value, usage={'total_tokens': 1}, llm_time=0.01)
        lrg.llm.init_llm = lambda config: Fake(config)
        try:
            with tempfile.TemporaryDirectory(prefix='proposed_v4_offline_') as temp:
                for mode, expected, count in [('PASS', 'kept_pass', 1), ('UNCERTAIN', 'kept_uncertain', 1),
                    ('FAIL', 'corrected', 2), ('INVALID', 'verifier_failed', 1)]:
                    config = dict(settings, output_path=str(Path(temp)/mode))
                    calls.clear()
                    trace = await runner.execute(config, source_idx='0000')
                    item = trace['items'][0]
                    assert item['status'] == expected and len(calls) == count
                    if mode != 'INVALID':
                        assert item['evidence_index'] == row['evidence_index']
                        assert item['resolved_evidence'] == resolve_evidence(item['feedback'], row['evidence_index'])
                    if mode == 'FAIL': assert calls == [('verifier', 2048), ('corrector', 4096)]
                    calls.clear()
                    await runner.execute(config, source_idx='0000')
                    assert not calls
                    cases.append(context+':'+expected)
        finally: runner.load_inputs = actual_load
    print(json.dumps(dict(real_llm_calls=0, rejected=rejected, cases=cases, budgets=budgets), indent=2))

try: loop.run_until_complete(main())
finally: loop.close()
