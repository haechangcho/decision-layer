import numpy as np
import statsmodels.api as sm


def check_data(data, outcome, treatment, confounders):
    """Stop if rows or variables cannot support the regression."""
    if data["entity_id"].isna().any() or data["entity_id"].duplicated().any():
        raise ValueError("Entity IDs must be present and unique.")
    columns = [outcome, treatment, *confounders]
    if len(set(columns)) != len(columns):
        raise ValueError("Analysis variables must use distinct columns.")
    if not np.isfinite(data[columns].to_numpy(dtype=float)).all():
        raise ValueError("Analysis variables must be finite and non-null.")
    if data[outcome].nunique() < 2:
        raise ValueError("The outcome must vary.")
    predictors = [name for name in columns if name != outcome]
    design = sm.add_constant(data[predictors], has_constant="add")
    if len(data) <= design.shape[1]:
        raise ValueError(
            "The number of rows must exceed the number of regression coefficients."
        )
    if np.linalg.matrix_rank(design) < design.shape[1]:
        raise ValueError(
            "Predictors are linearly dependent. Review the selected variables."
        )
