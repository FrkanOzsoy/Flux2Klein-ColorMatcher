FROM runpod/worker-comfyui:5.10.0-base

# Public custom-node packs used by the accompanying workflow. Clone errors
# fail the build, rather than relying on registry name resolution.
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

# The two in-house workflow nodes are in this one public repository.
# Pin the reviewed revision so later pushes do not silently alter the worker.
RUN git clone https://github.com/FrkanOzsoy/Flux2Klein-ColorMatcher.git \
      /comfyui/custom_nodes/Flux2Klein-ColorMatcher \
    && git -C /comfyui/custom_nodes/Flux2Klein-ColorMatcher checkout \
      cd818e335f7b13b73dbe97b41946b8a566da6861

# PhotoColorGrainMatch imports OpenCV and NumPy.
RUN python -c "import cv2, numpy" || uv pip install opencv-python-headless

# Assert the in-house node types register, then run ComfyUI's CPU startup check
# so missing custom-node imports fail the build.
#
# --cpu is REQUIRED, not optional: importing comfy.model_management runs a
# module-level VRAM probe (model_management.py:363) that calls
# torch.cuda.current_device(). A build container has no GPU, so without it:
#     RuntimeError: Found no NVIDIA driver on your system
# comfy only takes the CPU path when args.cpu is set (model_management.py:158)
# and cli_args fills args by parsing sys.argv - so the flag has to be on the
# command line. The base image's own smoke test below passes the same flag for
# the same reason.
#
# verify_nodes.py additionally fixes two earlier failures: it registers the
# module in sys.modules before exec_module (the relative import on line 1 of
# __init__.py cannot resolve otherwise) and puts /comfyui on sys.path (the
# pack imports comfy.*). Its docstring documents all three.
COPY verify_nodes.py /verify_nodes.py
RUN /opt/venv/bin/python /verify_nodes.py --cpu

RUN cd /comfyui && timeout 300 python main.py --quick-test-for-ci --cpu

# The official base image already supplies the RunPod handler and startup CMD.
