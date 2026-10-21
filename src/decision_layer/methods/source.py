"""Source evidence, captured at registration rather than re-reading after execution."""
from hashlib import sha256
import ast
import inspect
from pathlib import Path
from importlib.util import resolve_name
from ..core.models import MethodSource, SourceFile


def source_file(module):
    path = Path(inspect.getsourcefile(module) or '')
    if not path.is_file() or path.stat().st_size > 200_000:
        raise OSError('Source is unavailable or exceeds the inspection limit')
    content = path.read_text()
    return SourceFile(name=module.__name__, content=content, sha256=sha256(content.encode()).hexdigest())


def authoring_module(method, module, content):
    """A runnable slice of the selected asset, not a rewritten example or full file.

    Retain referenced definitions (including checks), imports and comments; apply the
    shared formatter only to this authoring projection. Full evidence stays exact.
    Unsupported dynamic registrations fall back to the full module; never silently
    drop code whose registration dependencies we cannot determine.
    """
    tree = ast.parse(content)
    # Unknown module initialization may affect the calculation. Do not remove it
    # just because it has no static reference from the selected function.
    for node in tree.body:
        if isinstance(node, ast.Expr) and not isinstance(node.value, ast.Constant):
            call = node.value
            if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                    and isinstance(call.func.value, ast.Name) and call.func.value.id == 'METHODS'
                    and call.func.attr == 'append'):
                return None
        if isinstance(node, (ast.If, ast.With, ast.Try, ast.While)):
            return None
        if isinstance(node, ast.For):
            # Previously published modules have this exact registration-only loop.
            expected = ('for _dl_registered_method in METHODS:\n'
                        '    _dl_registered_method.manifest = _dl_registered_method.manifest.model_copy(update=')
            if not ast.unparse(node).startswith(expected):
                return None
    definitions, imports = {}, []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            imports.append(node)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            definitions[node.name] = node
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    definitions[target.id] = node
    fn = getattr(method, 'fn', None)
    binding = next((name for name, value in vars(module).items() if value is method), None)
    # Older UI releases appended a METHODS list-comprehension filter. Select
    # the actual declaration before that generated bookkeeping assignment.
    registration = next((node for node in tree.body if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == 'METHODS' for target in node.targets)
        and isinstance(node.value, (ast.List, ast.Tuple))), None)
    selected = None
    if registration and isinstance(registration.value, (ast.List, ast.Tuple)):
        for item in registration.value.elts:
            if isinstance(item, ast.Call):
                named = any(k.arg == 'name' and isinstance(k.value, ast.Constant)
                            and k.value.value == method.manifest.name for k in item.keywords)
                uses_fn = fn and any(isinstance(arg, ast.Name) and arg.id == fn.__name__ for arg in item.args)
                if named or uses_fn:
                    selected = item
                    break
            elif binding and isinstance(item, ast.Name) and item.id == binding:
                selected = item
                break
    if selected is None and binding:
        selected = ast.Name(id=binding, ctx=ast.Load())
    if selected is None and fn is None and type(method).__name__ in definitions:
        selected = ast.Call(func=ast.Name(id=type(method).__name__,ctx=ast.Load()), args=[], keywords=[])
    if selected is None:
        return None
    needed, pending, nodes = set(), [selected], {}
    # Include future imports even when not directly referenced by a Name node.
    used_imports = {id(n): n for n in imports if isinstance(n, ast.ImportFrom) and n.module == '__future__'}
    while pending:
        node = pending.pop()
        for name in {n.id for n in ast.walk(node) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)} - needed:
            needed.add(name)
            if name in definitions and name != 'METHODS':
                dependency = definitions[name]
                nodes[id(dependency)] = dependency
                pending.append(dependency)
            for imp in imports:
                aliases = {a.asname or (a.name.split('.')[0] if isinstance(imp, ast.Import) else a.name) for a in imp.names}
                if name in aliases:
                    used_imports[id(imp)] = imp
    lines = content.splitlines(keepends=True)
    def original(node):
        if isinstance(node, ast.ImportFrom) and node.level:
            absolute = ast.ImportFrom(module=resolve_name('.' * node.level + (node.module or ''), module.__package__),
                                      names=node.names, level=0)
            return ast.unparse(absolute)
        start = min([node.lineno, *(d.lineno for d in getattr(node, 'decorator_list', []))])
        return ''.join(lines[start-1:node.end_lineno]).rstrip()
    ordered = sorted([*used_imports.values(), *nodes.values()], key=lambda n:n.lineno)
    parts = ''
    previous = None
    for node in ordered:
        adjacent_imports = isinstance(previous, (ast.Import, ast.ImportFrom)) and isinstance(node, (ast.Import, ast.ImportFrom))
        parts += ('\n' if adjacent_imports else '\n\n') if parts else ''
        parts += original(node)
        previous = node
    expression = ast.get_source_segment(content, selected) if hasattr(selected, 'lineno') else ast.unparse(selected)
    def byte_offset(node):
        return sum(len(line.encode()) for line in lines[:node.lineno-1]) + node.col_offset
    if isinstance(selected, ast.Call):
        for keyword in selected.keywords:
            if keyword.arg == 'version' and isinstance(keyword.value, ast.Constant):
                # UI releases apply version as metadata. The authoring projection
                # shows that effective version; exact original bytes remain in files.
                raw = ast.get_source_segment(content, keyword.value)
                offset = byte_offset(keyword.value) - byte_offset(selected)
                encoded = expression.encode()
                expression = (encoded[:offset] + repr(method.manifest.version).encode() + encoded[offset+len(raw.encode()):]).decode()
    from .formatting import format_python
    from .assets import AssetError
    focused = parts + '\n\nMETHODS = [' + expression + ']\n'
    try:
        return format_python(focused)
    except AssetError:
        # Source inspection must remain available even for unusual syntax/style.
        return focused


def capture_source(method):
    if getattr(method, 'source_snapshot', None):
        return method.source_snapshot.model_copy(deep=True)
    if method.manifest.implementation == 'skill':
        return None
    fn = getattr(method, 'fn', None)
    module = inspect.getmodule(fn if fn else type(method))
    try:
        entry = source_file(module)
        # Show first-level local calculation helpers, not a claim to trace a whole library.
        related, seen, size = [], {entry.name}, len(entry.content)
        for item in vars(module).values():
            if not inspect.isfunction(item):
                continue
            target = inspect.getmodule(item)
            name = getattr(target, '__name__', '')
            target_file = inspect.getsourcefile(target) if target else None
            local_helper = target_file and (Path(target_file).resolve().parent == Path(inspect.getsourcefile(module)).resolve().parent
                or name.startswith("_dl_project_"))
            if name in seen or not (name.startswith('decision_layer.methods.') or local_helper) or name.rsplit('.',1)[-1] in {'python','authoring','calculation'}:
                continue
            seen.add(name)
            helper = source_file(target)
            if size + len(helper.content) <= 200_000 and len(related) < 4:
                related.append(helper);size += len(helper.content)
        focused = authoring_module(method, module, entry.content)
        tree = ast.parse(entry.content)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level:
                node.module = resolve_name('.' * node.level + (node.module or ''), module.__package__)
                node.level = 0
        template = ast.unparse(tree)
        if hasattr(module, 'METHODS'):
            export = f"METHODS = [m for m in METHODS if m.manifest.name == {method.manifest.name!r}]"
        else:
            binding = next((name for name,value in vars(module).items() if value is method), None)
            export = f'METHODS = [{binding}]' if binding else f'METHODS = [{type(method).__name__}()]'
        # A source-bound builtin also retains the adapter which does the governed
        # extraction/checking; keep it in evidence, never in its authoring module.
        adapter = inspect.getmodule(type(method))
        if fn and adapter and adapter.__name__ not in seen and adapter.__name__.rsplit('.',1)[-1] not in {'python','calculation','authoring'}:
            related.append(source_file(adapter))
        return MethodSource(name=method.manifest.name, version=method.manifest.version, files=[entry,*related],
            authoring_content=focused, editor_content=focused or template+'\n\n'+export+'\n', available=True)
    except (OSError, TypeError, ValueError, SyntaxError):
        return MethodSource(name=method.manifest.name, version=method.manifest.version, available=False)
