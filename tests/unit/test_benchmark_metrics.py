import pytest
from examples.quickstart.evals.summarize import summarize, FIELDS


def trial(arm, rep=0, factor=1):
    return {'condition':arm,'case':'january','repeat':rep,'models':['fixed-model'],
        'completed':True,'numeric_screen':True,**{key:10*factor for key in FIELDS}}


def test_reports_increases_instead_of_inventing_savings():
    summary=summarize([trial('semantic'),trial('recipe',factor=2)])
    assert summary['paired_median_change_percent']['total_tokens']==100
    assert summary['recipe']['median']['total_tokens']==20


def test_rejects_incomplete_or_different_model_comparisons():
    with pytest.raises(ValueError): summarize([trial('semantic')])
    wrong=trial('recipe');wrong['models']=['other-model']
    with pytest.raises(ValueError): summarize([trial('semantic'),wrong])


def test_quality_failures_are_not_filtered_from_cost():
    wrong=trial('recipe',factor=3);wrong['numeric_screen']=False
    summary=summarize([trial('semantic'),wrong])
    assert summary['recipe']['numeric_screen_passes']==0
    assert summary['recipe']['total_cost_usd']==30
