"""Build-time assertion: the workflow's node types must be registered.

Usage:  /opt/venv/bin/python /verify_nodes.py

Run from INSIDE the image, where /comfyui is the ComfyUI checkout.

Two bugs this script exists to fix (both killed the Docker build):

1. `spec_from_file_location()` does NOT insert the module into `sys.modules`.
   A pack using a relative import (`from .sub import ...`) then dies on its
   first line with:
       ModuleNotFoundError: No module named '<pkg>'
   -> fixed by `sys.modules[NAME] = module` BEFORE `exec_module`.

2. The pack imports `comfy.model_management` (via Flux2klein_Ksampler_exp).
   `/comfyui` must be on sys.path or that import fails too.
   -> fixed by inserting COMFY_ROOT below.

ComfyUI's own loader does both, which is why these nodes import fine
interactively while a naive build-time probe does not.
"""
import importlib.util
import os
import sys

COMFY_ROOT = "/comfyui"
PACKAGE_NAME = "flux2_klein_color_matcher"
PACKAGE_DIR = os.path.join(COMFY_ROOT, "custom_nodes", "Flux2Klein-ColorMatcher")

# Node types this pack itself must provide. Types owned by the OTHER packs
# (ComfyUI-GGUF, ComfyUI_essentials, Inpaint-CropAndStitch) are not importable
# in isolation - they are covered by the --quick-test-for-ci step, which boots
# ComfyUI and loads the whole custom_nodes tree together.
REQUIRED = {
    "PhotoColorGrainMatch",
    "Flux2KleinColorAnchor",
}

if COMFY_ROOT not in sys.path:
    sys.path.insert(0, COMFY_ROOT)

init = os.path.join(PACKAGE_DIR, "__init__.py")
if not os.path.isfile(init):
    raise SystemExit("pack not found at %s" % PACKAGE_DIR)

spec = importlib.util.spec_from_file_location(
    PACKAGE_NAME, init, submodule_search_locations=[PACKAGE_DIR])
if spec is None or spec.loader is None:
    raise SystemExit("could not build a spec for %s" % init)

module = importlib.util.module_from_spec(spec)
sys.modules[PACKAGE_NAME] = module          # bug 1: required before exec_module
try:
    spec.loader.exec_module(module)
except Exception:
    sys.modules.pop(PACKAGE_NAME, None)
    raise

registered = set(module.NODE_CLASS_MAPPINGS)
print("Flux2Klein-ColorMatcher registered %d node types:" % len(registered))
for t in sorted(registered):
    print("  %s" % t)

missing = sorted(t for t in REQUIRED if t not in registered)
if missing:
    raise SystemExit("MISSING NODE TYPES: " + ", ".join(missing))

print("OK: all %d required node types present" % len(REQUIRED))
