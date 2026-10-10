# Query Method notebook example

Open `query_method.ipynb` in Jupyter or VS Code with a Python kernel that has this repository installed (`python -m pip install -e .`). `query_method.py` contains the same initial example in percent cell format; it uses notebook top-level await and is not a standalone command-line script. The two files are not automatically synchronized.

The example uses the existing Cube provider, MethodRegistry and RunEngine. It discovers metrics and dimensions from the caller-visible Cube API, registers a local Method, executes it directly, and previews a two-step Recipe with inspectable inputs, results, validation, DatasetSpecs and provider queries.

Configure these environment variables in the kernel environment:

| Variable | Value |
| --- | --- |
| `CUBE_API_URL` | Cube REST base URL ending in `/cubejs-api/v1` |
| `CUBE_TOKEN` | A Cube-accepted user token with a subject claim |
| `CUBE_INSTANCE` | Optional canonical instance name; defaults to `local` |
| `CUBE_METRIC` | A visible canonical measure ref from the catalog |
| `CUBE_DIMENSION` | A visible canonical dimension ref from the catalog |
| `CUBE_TIME_DIMENSION` | A visible canonical time dimension ref |
| `ANALYSIS_START` | Explicit start date, `YYYY-MM-DD` |
| `ANALYSIS_END` | Explicit end date, `YYYY-MM-DD` |

Run the discovery cells first to find references. You can assign the selected references and dates directly in the selection cell instead of using those environment variables. Keep the token out of saved notebook cells and outputs. The provider validates the actual combination of metric, dimensions and time basis.

The custom Method returns the largest N group values using provider aggregation and sorting. It does not calculate population shares, causal effects or significance. The direct execution cell uses a fresh ExecutionContext for debugging and produces a Result without saving a Run. Set a breakpoint inside `GroupMetric.run` when running this cell to inspect DatasetSpec construction and returned rows in the kernel.

The Recipe preview uses the ordinary RunEngine, including its execution policy, scope checks and query budgets. It stores Runs in memory for the current kernel only. Change `step_index=1` to `0` to inspect only the first step; each preview executes a new prefix and issues fresh queries. Engine jobs run in worker threads, so use direct execution for kernel breakpoints and preview evidence for pipeline inspection.

Registration is local to this notebook. Re-execute the registration cell after editing the Method. To debug an invalid input, the last cell checks that `limit=0` is rejected without another successful query. A provider failure can be inspected through `run.query_attempts`, result warnings and Run error evidence.

All notebook code cells were executed in order against a mocked Cube HTTP API. Verification covered catalog discovery, local registration, direct execution, the two-step preview, expected values, explicit period propagation, query evidence and invalid-parameter rejection. This is not a live Cube integration result or a statistical validity test.

The example intentionally exposes the current setup code. A contributor SDK should encapsulate provider connection, object discovery and isolated engine setup while continuing to execute these same contracts.
