"""ตรวจ schema/prompt/runner v3 แบบ offline ด้วยข้อมูล engineering และโมเดลจำลอง."""
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
from lrg.prompting.proposed import build_proposed_prompt, validate_verifier_feedback

VERSION = 'proposed-tax-v3'
def fixture(row, verdict='PASS'):
    node = row['nodes'][0]
    sources = {'QUESTION': row['question'], 'DRAFT_ANALYSIS': row['draft']['analysis'],
        'DRAFT_ANSWER': row['draft']['answer'], 'P1': (node.node if hasattr(node, 'node') else node).text}
    needed = {'I': ['QUESTION', 'DRAFT_ANSWER'], 'R': ['P1', 'DRAFT_ANALYSIS'],
        'A': ['QUESTION', 'P1', 'DRAFT_ANALYSIS'], 'C': ['DRAFT_ANALYSIS', 'DRAFT_ANSWER']}
    feedback = {'checks': [dict(axis=axis, verdict='PASS', reason='Synthetic interface test only.',
        evidence=[dict(source=s, quote=sources[s][:18]) for s in needed[axis]], revision=None) for axis in 'IRAC']}
    feedback['checks'][2]['verdict'] = verdict
    if verdict == 'FAIL':
        feedback['checks'][2]['revision'] = 'Synthetic supported correction.'
    return feedback

async def main():
    budgets, rejected, route_cases = [], 0, []
    for context in ('golden', 'retrieved'):
        settings = yaml.safe_load((ROOT/f'config/local/response/proposed_{context}_v3_engineering_10.yaml').read_text(encoding='utf-8'))
        loaded = runner.load_inputs(settings)
        _, _, model, rows, _ = loaded
        budget = runner.Budget(runner.tokenizer_file(), runner.CONTEXT_WINDOWS[model])
        for row in rows:
            if row['draft'] is None:
                continue
            inputs = {key: row[key] for key in ('question', 'nodes', 'draft')}
            for verdict in ('PASS', 'FAIL', 'UNCERTAIN'):
                validate_verifier_feedback(fixture(row, verdict), **inputs, version=VERSION)
            for mutation in ('pass_revision', 'fail_null', 'quote', 'source', 'long_quote', 'nested_issues', 'missing_axis'):
                bad = fixture(row)
                check = bad['checks'][0]
                if mutation == 'pass_revision': check['revision'] = 'Not allowed.'
                if mutation == 'fail_null': check['verdict'] = 'FAIL'
                if mutation == 'quote': check['evidence'][0]['quote'] = 'NO_SUCH_QUOTE_OFFLINE'
                if mutation == 'source': check['evidence'][0]['source'] = 'P99999'
                if mutation == 'long_quote': check['evidence'][0]['quote'] = row['question'][:81]
                if mutation == 'nested_issues': check['issues'] = []
                if mutation == 'missing_axis': bad['checks'].pop()
                try:
                    validate_verifier_feedback(bad, **inputs, version=VERSION)
                except ValueError:
                    rejected += 1
                else:
                    raise AssertionError(mutation)
            sizes = {}
            for stage in ('verifier', 'corrector'):
                extra = {} if stage == 'verifier' else {'feedback': fixture(row, 'FAIL')}
                prompt, structure = build_proposed_prompt(stage, **inputs, version=VERSION, **extra)
                sizes[stage] = budget.check(prompt, structure, settings[f'{stage}_max_tokens'])['required']
            budgets.append(dict(context=context, source_idx=row['source_idx'], **sizes))

        actual_load = runner.load_inputs
        runner.load_inputs = lambda settings: loaded
        row = rows[0]
        calls = []
        mode = 'PASS'
        class Fake:
            def __init__(self, config): self.config = config
            async def complete(self, **kwargs):
                stage = 'verifier' if kwargs['structure'].__name__ == 'IRACVerification' else 'corrector'
                calls.append((stage, self.config['max_tokens']))
                value = fixture(row, mode if mode != 'INVALID' else 'PASS') if stage == 'verifier' else deepcopy(row['draft'])
                if mode == 'INVALID': value['checks'][0]['revision'] = 'Invalid for PASS.'
                return dict(content=value, usage={'total_tokens': 1}, llm_time=0.01)
        lrg.llm.init_llm = lambda config: Fake(config)
        try:
            with tempfile.TemporaryDirectory(prefix='proposed_v3_offline_') as temp:
                for mode, expected, count in [('PASS', 'kept_pass', 1), ('UNCERTAIN', 'kept_uncertain', 1),
                                             ('FAIL', 'corrected', 2), ('INVALID', 'verifier_failed', 1)]:
                    config = dict(settings, output_path=str(Path(temp)/mode))
                    calls.clear()
                    trace = await runner.execute(config, source_idx='0000')
                    assert trace['items'][0]['status'] == expected and len(calls) == count
                    if mode == 'FAIL':
                        assert calls == [('verifier', 2048), ('corrector', 4096)]
                        readable = (Path(config['output_path'])/'diagnostics/source_0000/tax_proposed_trace.md').read_text(encoding='utf-8')
                        assert 'Synthetic supported correction.' in readable
                    calls.clear()
                    await runner.execute(config, source_idx='0000')
                    assert not calls
                    route_cases.append(f'{context}:{expected}')
        finally:
            runner.load_inputs = actual_load
    print(json.dumps(dict(real_llm_calls=0, rejected=rejected, routes=route_cases, budgets=budgets), indent=2))

try:
    loop.run_until_complete(main())
finally:
    loop.close()
