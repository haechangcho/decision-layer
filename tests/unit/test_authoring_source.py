"""The source a contributor copies must be runnable and actually used at execution."""
import importlib.util
import sys
import pandas as pd
from decision_layer.methods import registry, Scope
from decision_layer.methods.source import capture_source
from examples.methods.authoring.plain_python import METHODS, practice_session
from examples.methods.authoring.sample_data import METRIC, DIMENSION, DATE, DATES
from tests.support.semantic import RR, ctx


def import_source(path, content):
    path.write_text(content)
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[path.stem] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(path.stem, None)
    return module.METHODS[0]


async def test_native_authoring_module_excludes_other_methods_but_recreates_actual_calculation(tmp_path):
    # The same file contains other registrations, DoWhy code and a fixture session.
    source = capture_source(METHODS[0])
    assert source.authoring_content == source.editor_content
    assert 'def rank_groups' in source.authoring_content
    assert 'same_groups' not in source.authoring_content
    assert 'dowhy' not in source.authoring_content
    assert 'practice_session' not in source.authoring_content
    method = import_source(tmp_path/'focused_rank.py', source.editor_content)
    assert method.manifest == METHODS[0].manifest
    session = await practice_session()
    session.register(method, replace=True)
    result = (await session.run(method, value=METRIC, group=DIMENSION, scope=Scope(DATES,DATE))).result
    assert result.status == 'success'
    assert [row['rank'] for row in result.primary.data] == [1,2,2]


def test_focused_multiple_input_module_keeps_real_check_and_registration(tmp_path):
    source = capture_source(METHODS[1])
    assert 'def compare_periods' in source.editor_content
    assert 'def same_groups' in source.editor_content
    assert 'rank_groups' not in source.editor_content
    method = import_source(tmp_path/'focused_comparison.py',source.editor_content)
    assert method.manifest == METHODS[1].manifest
    assert len(method.checks) == 1


def test_prior_ui_module_is_editable_without_generated_filter_or_unrelated_recipe(tmp_path):
    from decision_layer.methods.assets import import_method
    code = '''from decision_layer.methods import python_method, DataInput
def calculate(data):
    return data
METHODS = [python_method(calculate, name="test.saved", version="1.0.0",
    inputs={"data":DataInput(measures=["value"])})]
def unrelated_recipe():
    return "Not part of this calculation"
METHODS = [m for m in METHODS if m.manifest.name == "test.saved"]
for _dl_registered_method in METHODS:
    _dl_registered_method.manifest = _dl_registered_method.manifest.model_copy(update={"version":"1.0.1"})
'''
    path=tmp_path/'prior_ui_module.py'
    # Keep the module registered while capturing source, like managed imports.
    path.write_text(code)
    spec=importlib.util.spec_from_file_location(path.stem,path)
    module=importlib.util.module_from_spec(spec);sys.modules[path.stem]=module
    try:
        spec.loader.exec_module(module)
        method=import_method(path.stem,'test.saved','1.0.1')
        source=capture_source(method)
        assert source.authoring_content
        assert 'unrelated_recipe' not in source.editor_content
        assert '_dl_registered_method' not in source.editor_content
        restored=import_source(tmp_path/'focused_saved.py',source.editor_content)
        assert restored.manifest == method.manifest
    finally:
        sys.modules.pop(path.stem,None)
