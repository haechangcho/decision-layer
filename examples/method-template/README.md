# Method contribution template

From the repository root, after installing development dependencies:

```bash
.venv/bin/pytest examples/method-template/test_method.py
```

`method.py` is a working minimal Method and `test_method.py` supplies a deterministic provider.
It is intentionally not registered in the production server and is not a new built-in capability.
Copy the structure, choose the correct Method family, add validation/refusal cases and register your reviewed implementation.
See [the contribution guide](../../docs/guides/methods.md).

Statistical and ML libraries are allowed in reviewed server-side Methods. Declare installation dependencies
in `pyproject.toml` (optional extras for heavy dependencies), use the canonical context for data extraction,
bound rows/columns and compute, and return typed artifacts, diagnostics and warnings.
Set `MethodOutput(runtime={"library-name": installed_version})` to record calculation dependencies.
Use established libraries instead of rewriting established estimators.

This does not authorize arbitrary runtime package installation, model-generated Python, untrusted pickle loading,
or user-uploaded executors. Changing the estimator or learned model may require a Method version change and
model provenance; a model artifact lifecycle is not provided by this template.
