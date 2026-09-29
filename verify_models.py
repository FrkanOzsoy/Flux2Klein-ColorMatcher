"""Fail the BUILD, not the job, if a model is missing or truncated.

The first live run failed with:

    VAELoader 122:       vae_name: 'flux2-vae.safetensors' not in ['pixel_space']
    UnetLoaderGGUF 138: unet_name: 'flux-2-klein-9b-Q4_K_M.gguf' not in []

ComfyUI validated the prompt against an EMPTY unet list because nothing was
mounted and nothing was baked in. The job then "completed" with
success_no_images - which looks like a success and is not.

The unet is now FP8 (core UNETLoader, folder `diffusion_models`) rather than
GGUF. The text encoder stays GGUF because CLIPLoaderGGUF has no safetensors
equivalent here, and it is the CUSTOM Qwen3-8B-Uncensor-v2 build.
"""
import os
import sys

sys.path.insert(0, "/comfyui")
import folder_paths  # noqa: E402

# (ComfyUI folder key, filename, expected bytes, human label)
REQUIRED = [
    ("diffusion_models", "flux-2-klein-9b-fp8.safetensors", 8996 * 1048576,
     "unet FP8 (UNETLoader)"),
    ("text_encoders", "Qwen3-8B-Uncensor-v2.Q4_K_M.gguf", 4794 * 1048576,
     "text encoder (CLIPLoaderGGUF)"),
    ("vae", "flux2-vae.safetensors", 320 * 1048576,
     "vae (VAELoader)"),
    ("loras", "bfs_head_v1_flux-klein_9b_step3500_rank128.safetensors", 632 * 1048576,
     "head LoRA (LoraLoader)"),
]

failed = []

for key, name, min_bytes, label in REQUIRED:
    base = {
        "diffusion_models": "/comfyui/models/diffusion_models/",
        "text_encoders": "/comfyui/models/text_encoders/",
        "vae": "/comfyui/models/vae/",
        "loras": "/comfyui/models/loras/",
    }[key]
    path = base + name

    exists = os.path.isfile(path)
    size = os.path.getsize(path) if exists else 0
    # allow 2% slack: HF reports the blob size, filesystems round
    truncated = exists and size < min_bytes * 0.98
    try:
        listed = name in folder_paths.get_filename_list(key)
    except Exception as exc:
        listed = False
        print("  ! could not list %s: %s" % (key, exc))

    print("  %-30s %-52s %8.1f MB  listed=%s"
          % (label, name[:52], size / 1048576, listed))

    if not exists:
        failed.append("%s MISSING at %s" % (name, path))
    elif truncated:
        failed.append("%s TRUNCATED: %.1f MB < expected ~%.1f MB (bad download?)"
                      % (name, size / 1048576, min_bytes / 1048576))
    elif not listed:
        failed.append("%s present but NOT visible to ComfyUI via '%s'" % (name, key))

if failed:
    sys.stderr.write("\nBUILD FAILURE - required weights are not usable:\n")
    for f in failed:
        sys.stderr.write("  - %s\n" % f)
    raise SystemExit(1)

total = sum(os.path.getsize(
    {  "diffusion_models": "/comfyui/models/diffusion_models/",
       "text_encoders": "/comfyui/models/text_encoders/",
       "vae": "/comfyui/models/vae/",
       "loras": "/comfyui/models/loras/"}[k] + n)
    for k, n, _b, _l in REQUIRED)
print("\nOK: all %d weights present, correctly sized and visible to ComfyUI (%.2f GB total)"
      % (len(REQUIRED), total / 1073741824))
