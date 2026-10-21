"""Bounded registration check for trusted operator Python; no analytical validation."""
import json
import sys
from .assets import import_method

if __name__ == '__main__':
    from ..project import prepare_project_imports
    prepare_project_imports(json.loads(sys.argv[4]) if len(sys.argv) > 4 else ())
    method = import_method(*sys.argv[1:4])
    print('DL_ASSET_MANIFEST:' + json.dumps(method.manifest.model_dump(mode='json')))
