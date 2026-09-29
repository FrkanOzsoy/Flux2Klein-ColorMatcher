FROM runpod/worker-comfyui:5.10.0-base

# ===========================================================================
# Public custom-node packs.
#
# ComfyUI-GGUF is still required: the TEXT ENCODER is a GGUF and is loaded with
# CLIPLoaderGGUF. Only the unet moved to FP8, which uses core UNETLoader.
# ===========================================================================
RUN git clone https://github.com/city96/ComfyUI-GGUF.git \
      /comfyui/custom_nodes/ComfyUI-GGUF \
    && git clone https://github.com/lquesada/ComfyUI-Inpaint-CropAndStitch.git \
      /comfyui/custom_nodes/ComfyUI-Inpaint-CropAndStitch \
    && git clone https://github.com/cubiq/ComfyUI_essentials.git \
      /comfyui/custom_nodes/ComfyUI_essentials \
    && git clone https://github.com/rgthree/rgthree-comfy.git \
      /comfyui/custom_nodes/rgthree-comfy \
    && for r in \
         /comfyui/custom_nodes/ComfyUI-GGUF/requirements.txt \
         /comfyui/custom_nodes/ComfyUI-Inpaint-CropAndStitch/requirements.txt \
         /comfyui/custom_nodes/ComfyUI_essentials/requirements.txt \
         /comfyui/custom_nodes/rgthree-comfy/requirements.txt; do \
         if [ -f "$r" ]; then uv pip install -r "$r" || exit 1; fi; \
       done

# The two in-house workflow nodes. Pin the reviewed revision.
RUN git clone https://github.com/FrkanOzsoy/Flux2Klein-ColorMatcher.git \
      /comfyui/custom_nodes/Flux2Klein-ColorMatcher \
    && git -C /comfyui/custom_nodes/Flux2Klein-ColorMatcher checkout \
      cd818e335f7b13b73dbe97b41946b8a566da6861

RUN python -c "import cv2, numpy" || uv pip install opencv-python-headless

# ===========================================================================
# Build-time assertion that the in-house node types register.
#
# Must be a script, not `python -c`, and MUST get --cpu:
#  1. spec_from_file_location() does not register the module in sys.modules, so
#     the relative import on line 1 of __init__.py raised
#     ModuleNotFoundError: No module named 'flux2_klein_color_matcher'.
#  2. /comfyui must be on sys.path because the pack imports comfy.*.
#  3. comfy/options.py ships args_parsing = False and cli_args then runs
#     parser.parse_args([]), DISCARDING command-line flags. Only main.py calls
#     comfy.options.enable_args_parsing(); verify_nodes.py does the same, which
#     is what makes args.cpu True. Without it, model_management's import-time
#     VRAM probe calls torch.cuda and the build dies with
#     "Found no NVIDIA driver on your system".
# ===========================================================================
COPY verify_nodes.py /verify_nodes.py
RUN /opt/venv/bin/python /verify_nodes.py --cpu

# ===========================================================================
# Model weights, fetched from HuggingFace at BUILD time.
#
# Why not COPY from the repo: GitHub rejects files over 100 MB and Git LFS caps
# at 5 GB per file. These total ~14.7 GB, so they can never live in git - which
# is why this image is built from a commit on Runpod's own builders rather than
# locally.
#
# All four repos are ungated, so plain wget works with no token. Sizes are
# asserted by verify_models.py below.
#
# Destinations are ComfyUI's NATIVE search paths, not the worker's
# extra_model_paths.yaml volume mappings. That matters: that yaml maps
# `unet -> /runpod-volume/models/unet/`, but UNETLoader reads the
# `diffusion_models` folder, so a volume at models/unet would never be listed.
# Writing to the native paths sidesteps the mapping entirely.
# ===========================================================================
ARG HF_BASE=https://huggingface.co
ENV HF_BASE=${HF_BASE}

# curl, not wget: -f fails on HTTP errors, -L follows the CDN redirect, and
# --retry/-C resume a dropped transfer. The first attempt at the LoRA stalled
# for 40s, produced 0 bytes and STILL exited 0, so `set -e` did not catch it -
# wget alone is not reliable enough for a one-shot 632 MB pull from an
# untested mirror. verify_models.py is the real gate; this just makes the
# download itself likely to succeed on the first try.
RUN set -eux; \
    mkdir -p /comfyui/models/diffusion_models /comfyui/models/text_encoders \
             /comfyui/models/vae /comfyui/models/loras; \
    fetch() { \
      dest="$1"; url="$2"; \
      echo ">>> $url"; \
      curl -fL --retry 5 --retry-delay 5 --retry-connrefused --retry-all-errors \
           -C - --connect-timeout 30 --speed-time 60 --speed-limit 1024 \
           -o "$dest" "$url"; \
      test -s "$dest" || { echo "EMPTY DOWNLOAD: $dest"; exit 1; }; \
    }; \
    \
    fetch /comfyui/models/diffusion_models/flux-2-klein-9b-fp8.safetensors \
      "${HF_BASE}/MIUProject/FLUX.2-klein-9b-fp8/resolve/main/flux-2-klein-9b-fp8.safetensors"; \
    fetch /comfyui/models/text_encoders/Qwen3-8B-Uncensor-v2.Q4_K_M.gguf \
      "${HF_BASE}/mradermacher/Qwen3-8B-Uncensor-v2-GGUF/resolve/main/Qwen3-8B-Uncensor-v2.Q4_K_M.gguf"; \
    fetch /comfyui/models/vae/flux2-vae.safetensors \
      "${HF_BASE}/Thonatossss/flux2-vae/resolve/main/flux2-vae.safetensors"; \
    fetch /comfyui/models/loras/bfs_head_v1_flux-klein_9b_step3500_rank128.safetensors \
      "${HF_BASE}/bond12321/bfs-head-klein9b/resolve/main/bfs_head_v1_flux-klein_9b_step3500_rank128.safetensors"

# Fail the BUILD, not the job, if anything is missing or truncated. The first
# live run failed with 'unet_name not in []' and then reported
# success_no_images, which looks like a success and is not.
COPY verify_models.py /verify_models.py
RUN /opt/venv/bin/python /verify_models.py

# Full import-graph smoke test, CPU only.
RUN cd /comfyui && timeout 300 python main.py --quick-test-for-ci --cpu

# The official base image already supplies the RunPod handler and startup CMD.
