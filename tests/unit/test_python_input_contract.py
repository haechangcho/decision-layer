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
    assert method.manifest.version == '1.1.0'
    assert method.manifest.data_inputs == method.inputs
    source = capture_source(method).editor_content
    function = next(node for node in ast.parse(source).body if isinstance(node, ast.FunctionDef) and node.name == 'analyze')
    assert function.args.args[0].arg == 'data' and 'ctx.' not in source and 'async def' not in source
    restored = import_source(tmp_path / (name.split('.')[-1] + '_copy.py'), source)
    assert restored.manifest == method.manifest
    assert restored.fn is not method.fn  # This is editable code, not an illustrative wrapper.
    assert registry.get(name, '1.0.0').manifest.version == '1.0.0'


async def native_trial(name, version=None, bindings=None):
    from tests.unit.test_dowhy_matching import sample
    frame = sample()
    spec = DatasetSpec(grain='entity', measures=[M], dimensions=[TREAT, BASELINE], entity=UNIT,
        time=TimeScope(dimension=DATE, date_range=FEB), limit_rows=50001)
    provider = FixtureProvider(catalog(), [QueryFixture(spec, frame[['outcome','treatment','baseline','unit']].values.tolist())])
    session = await MethodSession.fixture(provider)
    session.registry = registry.copy()
    method = registry.get(name, version)
    # Explicitly select the version for this trial; the application's registry is unchanged.
    session.register(method, replace=True)
    trial = await session.run(name, scope=Scope(FEB, DATE),
        **(bindings or dict(outcome=M, treatment=TREAT, confounders=[BASELINE], unit=UNIT)))
    return trial


@pytest.mark.parametrize('name', ['stats.binary_matching', 'stats.regression_adjustment'])
async def test_native_versions_preserve_estimate_diagnostics_and_cube_specs(name):
    pytest.importorskip('dowhy')
    current, old = await native_trial(name), await native_trial(name, '1.0.0')
    assert current.result.status == old.result.status == 'success'
    assert current.result.primary == old.result.primary
    assert current.result.provides == old.result.provides
    assert all(check in current.result.validation for check in old.result.validation)
    assert [a.spec for a in current.attempts] == [a.spec for a in old.attempts]
    assert current.result.primary.data['causal_claim'] == 'not_established'
    mapping = json.loads(current.result.provenance.runtime['python.resolved_inputs'])['data']
    assert mapping['semantic_refs']['confounders_0'] == BASELINE
    assert mapping['grain'] == 'entity'
    assert mapping['columns'] == ['unit', 'treatment', 'confounders_0', 'outcome']
    assert current.result.provenance.runtime['python.function_sha256'] != 'unavailable'


async def test_single_ref_for_list_role_still_produces_stable_columns():
    pytest.importorskip('dowhy')
    trial = await native_trial('stats.binary_matching', bindings={
        'outcome': [M], 'treatment': TREAT, 'confounders': BASELINE, 'unit': UNIT})
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
        assert registry.get(name).manifest.implementation == 'python'


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
