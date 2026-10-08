"""ตรวจ verifier v2 กับข้อมูล engineering และโมเดลจำลอง โดยปิด network."""
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
    raise AssertionError("Network/real LLM forbidden")
socket.socket.connect = socket.socket.connect_ex = socket.create_connection = forbidden
import yaml
import openai
openai.OpenAI = openai.AsyncOpenAI = forbidden
import lrg.llm
from script import response_proposed as runner
from lrg.prompting.proposed import build_proposed_prompt, validate_verifier_feedback

VERSION = 'proposed-tax-v2'
def fixture(row, verdict='PASS'):
    node = row['nodes'][0]
    sources = {'QUESTION': row['question'], 'DRAFT_ANALYSIS': row['draft']['analysis'],
               'DRAFT_ANSWER': row['draft']['answer'], 'P1': (node.node if hasattr(node, 'node') else node).text}
    requirements = {'I': ['QUESTION', 'DRAFT_ANSWER'], 'R': ['P1', 'DRAFT_ANALYSIS'],
                    'A': ['QUESTION', 'P1', 'DRAFT_ANALYSIS'], 'C': ['DRAFT_ANALYSIS', 'DRAFT_ANSWER']}
    feedback = {'checks': [dict(axis=axis, verdict='PASS', reason='Synthetic interface test only.',
                 evidence=[dict(source=source, quote=sources[source][:18]) for source in requirements[axis]], issues=[])
                 for axis in 'IRAC']}
    check = feedback['checks'][2]
    check['verdict'] = verdict
    if verdict == 'FAIL':
        check['issues'] = [dict(draft_field='analysis', draft_quote=sources['DRAFT_ANALYSIS'][:18],
            problem='Synthetic material issue.', evidence=deepcopy(check['evidence']), revision='Synthetic revision.')]
    return feedback

def reject(action):
    try:
        action()
    except ValueError:
        return
    raise AssertionError('Expected validation rejection')

async def main():
    cases, budgets = [], []
    first = None
    for context in ('golden', 'retrieved'):
        settings = yaml.safe_load((ROOT / f'config/local/response/proposed_{context}_v2_engineering_10.yaml').read_text(encoding='utf-8'))
        loaded = runner.load_inputs(settings)
        _, _, model, rows, _ = loaded
        budget = runner.Budget(runner.tokenizer_file(), runner.CONTEXT_WINDOWS[model])
        for row in rows:
            if row['draft'] is None:
                continue
            inputs = {key: row[key] for key in ('question', 'nodes', 'draft')}
            feedback = fixture(row)
            validate_verifier_feedback(feedback, **inputs, version=VERSION)
            bad = deepcopy(feedback)
            del bad['checks'][0]['evidence']
            reject(lambda: validate_verifier_feedback(bad, **inputs, version=VERSION))
            bad = deepcopy(feedback)
            bad['checks'][0]['evidence'][0]['quote'] = 'NONEXISTENT_QUOTE_FOR_OFFLINE_TEST'
            reject(lambda: validate_verifier_feedback(bad, **inputs, version=VERSION))
            bad = deepcopy(feedback)
            bad['checks'][2]['evidence'] = [bad['checks'][2]['evidence'][2]]
            reject(lambda: validate_verifier_feedback(bad, **inputs, version=VERSION))
            old = deepcopy(feedback)
            for check in old['checks']:
                del check['evidence']
            validate_verifier_feedback(old, **inputs)  # v1 still accepts its original schema
            sizes = {}
            for stage in ('verifier', 'corrector'):
                kwargs = {} if stage == 'verifier' else {'feedback': fixture(row, 'FAIL')}
                prompt, schema = build_proposed_prompt(stage, **inputs, version=VERSION, **kwargs)
                sizes[stage] = budget.check(prompt, schema, settings[f'{stage}_max_tokens'])['required']
            budgets.append(dict(context=context, source_idx=row['source_idx'], **sizes))
        if first is None:
            first = settings, loaded

    settings, loaded = first
    row = loaded[3][0]
    actual_load = runner.load_inputs
    runner.load_inputs = lambda settings: loaded
    calls = []
    mode = 'PASS'
    class Fake:
        def __init__(self, config):
            self.config = config
        async def complete(self, **kwargs):
            stage = 'verifier' if kwargs['structure'].__name__ == 'IRACVerification' else 'corrector'
            calls.append((stage, self.config['max_tokens']))
            value = fixture(row, mode) if stage == 'verifier' else deepcopy(row['draft'])
            if mode == 'INVALID' and stage == 'verifier':
                value = fixture(row)
                del value['checks'][0]['evidence']
            return dict(content=value, usage={'total_tokens': 1}, llm_time=0.01)
    lrg.llm.init_llm = lambda config: Fake(config)
    try:
        with tempfile.TemporaryDirectory(prefix='proposed_v2_offline_') as temp:
            for mode, state, count in [('PASS', 'kept_pass', 1), ('UNCERTAIN', 'kept_uncertain', 1),
                                       ('FAIL', 'corrected', 2), ('INVALID', 'verifier_failed', 1)]:
                config = dict(settings, output_path=str(Path(temp) / mode))
                calls.clear()
                trace = await runner.execute(config, source_idx='0000')
                assert trace['items'][0]['status'] == state
                assert len(calls) == count
                if mode == 'FAIL':
                    assert calls == [('verifier', 2048), ('corrector', 4096)]
                calls.clear()
                await runner.execute(config, source_idx='0000')
                assert not calls
                cases.append(state)
    finally:
        runner.load_inputs = actual_load
    print(json.dumps(dict(real_llm_calls=0, cases=cases, rejection_checks=57, budgets=budgets), ensure_ascii=False, indent=2))

try:
    loop.run_until_complete(main())
finally:
    loop.close()
