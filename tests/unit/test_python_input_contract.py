"""The ordinary authoring path must preserve data safety and pinned analyses."""
import json
import ast
import pytest

from decision_layer.core.models import DataInput, DatasetSpec, TimeScope
from decision_layer.methods import InvalidBinding, Scope, python_method, registry
from decision_layer.methods.python import PythonMethod
from decision_layer.methods.source import capture_source
from decision_layer.dev import MethodSession
from decision_layer.testing import FixtureProvider, QueryFixture
from tests.unit.test_authoring_source import import_source
from tests.support.methods.cases import catalog, M, TREAT, BASELINE, UNIT, DATE, FEB


@pytest.mark.parametrize('name', ['stats.binary_matching', 'stats.regression_adjustment'])
def test_default_statistical_authoring_is_a_real_ordinary_function(name, tmp_path):
    method = registry.get(name)
    assert isinstance(method, PythonMethod)
    assert method.manifest.version == '2.1.0'
    assert method.manifest.data_inputs == method.inputs
    source = capture_source(method).editor_content
    function = next(node for node in ast.parse(source).body if isinstance(node, ast.FunctionDef) and node.name == ('matching' if name.endswith('matching') else 'ols'))
    assert function.args.args[0].arg == 'data' and 'ctx.' not in source and 'async def' not in source
    restored = import_source(tmp_path / (name.split('.')[-1] + '_copy.py'), source)
    assert restored.manifest == method.manifest
    assert restored.fn is not method.fn  # This is editable code, not an illustrative wrapper.
    with pytest.raises(InvalidBinding):
        registry.get(name, '1.0.0')


async def native_trial(name, bindings=None):
    import numpy as np
    x = np.tile(np.linspace(-1, 1, 100), 2)
    treatment = np.repeat([0, 1], 100)
    rows = [[float(3*x[i]+2*treatment[i]), int(treatment[i]), float(x[i]), str(i)] for i in range(200)]
    spec = DatasetSpec(grain='entity', measures=[M], dimensions=[TREAT, BASELINE], entity=UNIT,
        time=TimeScope(dimension=DATE, date_range=FEB), limit_rows=50001)
    provider = FixtureProvider(catalog(), [QueryFixture(spec, rows)])
    session = await MethodSession.fixture(provider)
    method = registry.get(name)
    session.register(method)
    return await session.run(name, scope=Scope(FEB, DATE),
        **(bindings or dict(outcome=M, treatment=TREAT, confounders=[BASELINE], entity_id=UNIT)))


@pytest.mark.parametrize('name', ['stats.binary_matching', 'stats.regression_adjustment'])
async def test_current_calculations_preserve_known_answer_and_query_evidence(name):
    trial = await native_trial(name)
    assert trial.result.status == 'success'
    assert trial.result.primary.data['value'] == pytest.approx(2)
    assert trial.result.primary.data['causal_claim'] == 'not_established'
    assert len(trial.attempts) == 1
    mapping = json.loads(trial.result.provenance.runtime['python.resolved_inputs'])['data']
    assert mapping['semantic_refs']['confounders_0'] == BASELINE
    assert mapping['grain'] == 'entity'
    assert trial.result.provenance.runtime['python.function_sha256'] != 'unavailable'


async def test_single_ref_for_list_role_still_produces_stable_columns():
    trial = await native_trial('stats.binary_matching', bindings={
        'outcome': [M], 'treatment': TREAT, 'confounders': BASELINE, 'entity_id': UNIT})
    assert trial.result.status == 'success'
    assert trial.result.primary.data['value'] == pytest.approx(2)


async def test_missing_binding_does_not_query_or_guess():
    from examples.methods.authoring.plain_python import practice_session, METHODS
    from examples.methods.authoring.sample_data import METRIC, DATES, DATE as TIME
    session = await practice_session()
    session.register(METHODS[0])
    with pytest.raises(InvalidBinding, match='group'):
        await session.run(METHODS[0], value=METRIC, scope=Scope(DATES, TIME))
    assert session.provider.calls == []


async def test_mixed_measure_is_checked_before_calculation():
    from decision_layer.core.models import RoleSpec
    from tests.support.methods.cases import RATE
    def never(data):
        raise AssertionError('Invalid input reached calculation')
    method = python_method(never, name='test.mixed', version='1.0.0', inputs={
        'data': DataInput(entity='unit', measures=['outcome'], columns={
            'treatment': RoleSpec(kind='dimension', accepted_kinds=['dimension','measure'])})})
    spec = DatasetSpec(grain='entity', entity=UNIT, measures=[M, RATE],
        time=TimeScope(dimension=DATE, date_range=FEB), limit_rows=50001)
    session = await MethodSession.fixture(FixtureProvider(catalog(), [QueryFixture(spec, [[3,float('nan'),'a']])]))
    session.register(method)
    result = (await session.run(method, outcome=M, treatment=RATE, unit=UNIT, scope=Scope(FEB,DATE))).result
    assert result.status == 'refused' and result.primary is None
    assert any(check.code == 'FINITE_MEASURES' and check.status == 'fail' for check in result.validation)


def test_compatibility_choices_remain_explicit_only():
    public = {m.name for m in registry.manifests()}
    for name in ('query.aggregate','query.trend','query.drilldown','query.peer_comparison','causal.cem'):
        assert name not in public
        with pytest.raises(InvalidBinding):
            registry.get(name)


def warn_and_return(data):
    import warnings
    warnings.warn('Library diagnostic retained', RuntimeWarning)
    return data


async def test_ordinary_worker_preserves_library_warnings():
    import time
    from decision_layer.methods.context import ExecutionContext
    from decision_layer.methods.python import _execute_python
    from decision_layer.core.periods import ExecutionPolicy
    from decision_layer.semantic.credentials import AnonymousServiceCredentials
    from tests.unit.test_method_assets import data_provider
    async def persist():
        pass
    provider = data_provider()
    context = ExecutionContext(provider, AnonymousServiceCredentials(), provider.catalog,
        execution_policy=ExecutionPolicy(), persist_attempts=persist)
    context._started = time.monotonic()
    method = python_method(warn_and_return, name='test.warnings', version='1.0.0',
        inputs={'data':DataInput(measures=['value'])})
    result = await context.compute(_execute_python, method.fn, {'data':[{'value':3}]},
        method.inputs, {}, (), method.output, method.adapt)
    assert 'Library diagnostic retained' in result.warnings
    assert result.primary.data == [{'value':3}]
