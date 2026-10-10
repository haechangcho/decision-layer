"""Check result contracts, not the truth of caller-written sentences."""
from ..methods import InvalidBinding


def validate_outcomes(run, conclusion):
    outcomes = conclusion.goal_outcomes if conclusion else []
    by_id = {outcome.goal_id: outcome for outcome in outcomes}
    if len(by_id) != len(outcomes) or set(by_id) != {goal.id for goal in run.goals}:
        raise InvalidBinding("Record one outcome for every analysis goal.")
    for goal in run.goals:
        outcome = by_id[goal.id]
        if any(index < 0 or index >= len(run.steps) for index in outcome.step_indices):
            raise InvalidBinding("Goal evidence must reference recorded step indices.")
        records = [run.steps[index] for index in outcome.step_indices]
        if outcome.status == "supported":
            successful = [record.result for record in records if record.result.status == "success" and record.result.primary is not None]
            matching = [result for result in successful
                        if (goal.interpretation == "descriptive" or result.interpretation == goal.interpretation)
                        and set(goal.semantic_refs) <= set(result.provenance.semantic_refs)]
            provided = set().union(*(set(result.provides) for result in matching))
            refs = set().union(*(set(result.provenance.semantic_refs) for result in matching))
            if not matching or not set(goal.required_capabilities) <= provided or not set(goal.semantic_refs) <= refs:
                raise InvalidBinding("The recorded results do not support this goal's required contract.", goal_id=goal.id)
        elif not outcome.reason.strip():
            raise InvalidBinding("Unresolved goals need a reason.", goal_id=goal.id)
