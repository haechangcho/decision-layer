"""Bounded registration check for trusted operator Python; no analytical validation."""
import json
import sys
from .assets import import_method

if __name__ == '__main__':
    method = import_method(*sys.argv[1:])
    print('DL_ASSET_MANIFEST:' + json.dumps(method.manifest.model_dump(mode='json')))
