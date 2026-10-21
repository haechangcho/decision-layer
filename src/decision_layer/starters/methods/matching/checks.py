import numpy as np
from decision_layer.methods.context import Refused


def check_data(data, outcome, treatment, confounders):
    """Check the two groups and required observations."""
    if data["entity_id"].isna().any() or data["entity_id"].duplicated().any():
        raise ValueError("Entity IDs must be present and unique.")
    columns = [outcome, treatment, *confounders]
    if len(set(columns)) != len(columns):
        raise ValueError("Analysis variables must use distinct columns.")
    if not confounders:
        raise ValueError("Select at least one covariate.")
    values = data[columns]
    if not np.isfinite(values.to_numpy(dtype=float)).all():
        raise ValueError("Analysis variables must be finite and non-null.")
    if set(data[treatment].unique()) != {0, 1}:
        raise ValueError("Treatment must contain both 0 and 1, with no other values.")
    if data.groupby(treatment).size().min() < 30:
        raise ValueError("Each group needs at least 30 observations.")


def standardize(covariates):
    """Put variables on a comparable scale before measuring distance."""
    scale = covariates.std(ddof=0)
    if not np.isfinite(scale).all() or (scale <= 0).any():
        raise Refused("Covariates must have finite, positive variation.")
    return (covariates - covariates.mean()) / scale


def check_overlap(probabilities):
    """Stop when group membership is almost entirely predicted by the variables."""
    if (probabilities < 0.05).any() or (probabilities > 0.95).any():
        raise Refused("The groups have insufficient propensity overlap.")


def check_matches(covariates, treated, matched_positions, distances):
    """Require enough controls, nearby matches and balanced variables."""
    if len(set(matched_positions)) < 30:
        raise Refused("At least 30 distinct matched controls are required.")
    if float(distances.max()) > 1.0:
        raise Refused("Matched observations exceed the permitted distance.")
    target = covariates.loc[treated]
    control = covariates.loc[~treated]
    pooled = np.sqrt((target.var(ddof=1) + control.var(ddof=1)) / 2)
    if not np.isfinite(pooled).all() or (pooled <= 0).any():
        raise Refused("Covariates must vary within groups.")
    balance = (target.mean() - covariates.iloc[matched_positions].mean()) / pooled
    if balance.abs().max() > 0.1:
        raise Refused("Matched covariate imbalance exceeds the permitted threshold.")
    return balance
