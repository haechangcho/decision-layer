async def execute_notebook(path, monkeypatch):
    import ast
    import inspect
    import json
    namespace = {"__name__": "__notebook__"}
    for index, cell in enumerate(json.loads(path.read_text())["cells"]):
        if cell["cell_type"] == "code":
            source = "".join(cell["source"]) if isinstance(cell["source"], list) else cell["source"]
            code = compile(source, f"{path.name}:cell-{index}", "exec", flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)
            pending = eval(code, namespace)
            if inspect.isawaitable(pending):
                await pending
    return namespace
