"""Terminate server statistical fits without shipping provider credentials to children."""
from __future__ import annotations
from ..i18n import _
import asyncio
import multiprocessing
import time
import warnings
from .context import Refused


def _worker(connection, fn, args, locale):
    # Spawn inherits the server environment. Keep only library-runtime settings;
    # provider tokens/database credentials are neither arguments nor fit-time env.
    import os
    allowed = {name: value for name, value in os.environ.items() if name in
               {"PATH", "PYTHONPATH", "TMPDIR", "TEMP", "TMP", "MPLCONFIGDIR",
                "LANG", "LC_ALL", "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS"}}
    os.environ.clear()
    os.environ.update(allowed)
    os.environ["MPLBACKEND"] = "Agg"
    from ..i18n import set_locale
    set_locale(locale)
    try:
        with warnings.catch_warnings(record=True) as observed:
            warnings.simplefilter("always")
            result = fn(*args)
        if isinstance(result, dict):
            result["backend_warnings"] = list(dict.fromkeys(str(warning.message) for warning in observed))[:10]
        else:
            from .base import MethodOutput
            if isinstance(result, MethodOutput):
                # Ordinary functions return through the output adapter in this
                # worker. Preserve library warnings on the canonical Result too.
                result.warnings.extend(message for message in
                    list(dict.fromkeys(str(warning.message) for warning in observed))[:10]
                    if message not in result.warnings)
        connection.send({"ok": True, "result": result})
    except Refused as exc:
        connection.send({"ok": False, "refused": True, "message": exc.message})
    except BaseException as exc:
        connection.send({"ok": False, "refused": False, "type": type(exc).__name__})
    finally:
        connection.close()


async def compute(ctx, fn, args):
    # A local trial deliberately stays in the caller's process for breakpoints.
    if ctx.persist_attempts is None:
        return fn(*args)
    limit = ctx.execution_policy.deadline_seconds if ctx.execution_policy else 120
    remaining = limit - (time.monotonic() - ctx._started)
    if remaining <= 0:
        raise Refused(_("The statistical computation exceeded the execution deadline"))
    mp = multiprocessing.get_context("spawn")
    parent, child = mp.Pipe(duplex=False)
    from ..i18n import get_locale
    process = mp.Process(target=_worker, args=(child, fn, args, get_locale()), daemon=True)
    process.start()
    child.close()
    deadline = time.monotonic() + remaining
    try:
        while not parent.poll():
            if time.monotonic() >= deadline:
                raise Refused(_("The statistical computation exceeded the execution deadline"))
            if not process.is_alive():
                raise RuntimeError("The statistical worker exited without a result")
            await asyncio.sleep(.01)
        try:
            packet = parent.recv()
        except EOFError as exc:
            raise RuntimeError("The statistical worker exited without a result") from exc
        if not packet["ok"]:
            if packet["refused"]:
                raise Refused(packet["message"])
            raise RuntimeError(f"Statistical backend failed ({packet['type']})")
        return packet["result"]
    finally:
        parent.close()
        if process.is_alive():
            process.terminate()
        process.join(timeout=2)
        if process.is_alive():
            process.kill()
            process.join(timeout=2)
