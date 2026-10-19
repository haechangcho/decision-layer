# A complete Method project

Python and Skill definitions share `workshop_project/methods/`:

- `rank/method.py`: `workshop_project.rank`, a fixed-column ranking function.
- `ols/method.py`: `workshop_project.ols`, an ordinary OLS function taking column names.
- `metric_review/SKILL.md`: `workshop_project.metric_review`, recorded query guidance.

From the repository root, using its Python environment:

```sh
python -m decision_layer check --project examples/methods/project
python -m decision_layer list --project examples/methods/project
# Start the API with this project when ready:
python -m decision_layer serve --project examples/methods/project --reload
```

`list` prints the path that defines each Method. `check` validates registration,
not analytical correctness. The [notebook](../../../docs/tutorials/methods/write_your_method.en.ipynb)
introduces the same ranking and OLS functions. This directory shows how to save
them as project files; Web and MCP use the server's project registry.

Start a fresh project with `decision-layer init my_team`. Add entries with
`decision-layer new python <name>` or `decision-layer new skill <name>`.
Project code is imported at check/startup. Deploy reviewed files and dependencies,
set `DL_PROJECT_DIR` to the project root, and restart the API.

[Project guide](../../../docs/guides/method-projects.md) · [한국어](README.ko.md)
