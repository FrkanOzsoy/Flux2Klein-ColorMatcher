"""Build-time assertion: the workflow's node types must be registered.

Usage:  /opt/venv/bin/python /verify_nodes.py --cpu

MUST be run with --cpu. Three separate things have broken this build, and each
is documented below so the next failure is diagnosable from the log alone:

1. `spec_from_file_location()` does NOT insert the module into `sys.modules`.
   A pack using a relative import (`from .sub import ...`) then dies on its
   first line with:
       ModuleNotFoundError: No module named '<pkg>'
   -> fixed by `sys.modules[NAME] = module` BEFORE `exec_module`.

2. The pack imports `comfy.*`, so /comfyui must be on sys.path.
   -> fixed by inserting COMFY_ROOT below.

3. Importing `comfy.model_management` runs a module-level VRAM probe that
   calls `torch.cuda.current_device()`. A docker build has NO GPU, so that
   raises:
       RuntimeError: Found no NVIDIA driver on your system
   -> `comfy.model_management` only takes the CPU path when `args.cpu` is set
      (model_management.py: `if args.cpu: cpu_state = CPUState.CPU`), and
      `comfy.cli_args` populates `args` by parsing **sys.argv**. So the
      script cannot set this from the inside - it must be passed `--cpu` on
      the command line. The base image's own smoke test does the same thing
      with `python main.py --quick-test-for-ci --cpu`.

ComfyUI's own loader does 1 and 2, which is why these nodes import fine
interactively while a naive build-time probe does not.
"""
import importlib.util
import os
import sys

# Fail loudly and early if someone drops the flag that makes this work.
if "--cpu" not in sys.argv:
    sys.stderr.write(
        "verify_nodes.py must be run with --cpu (ComfyUI's import-time VRAM "
        "probe calls torch.cuda, which has no GPU inside a build container).\n"
    )
    raise SystemExit(2)

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
