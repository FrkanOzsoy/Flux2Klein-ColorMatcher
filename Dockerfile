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

# PhotoColorGrainMatch imports OpenCV and NumPy. Test the registrations, then
# run ComfyUI's CPU startup check so missing custom-node imports fail the build.
RUN python -c "import cv2, numpy" || uv pip install opencv-python-headless
RUN python -c "import importlib.util; p='/comfyui/custom_nodes/Flux2Klein-ColorMatcher/__init__.py'; s=importlib.util.spec_from_file_location('flux2_klein_color_matcher',p,submodule_search_locations=['/comfyui/custom_nodes/Flux2Klein-ColorMatcher']); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); assert {'PhotoColorGrainMatch','Flux2KleinColorAnchor'} <= set(m.NODE_CLASS_MAPPINGS)"
RUN cd /comfyui && timeout 300 python main.py --quick-test-for-ci --cpu

# The official base image already supplies the RunPod handler and startup CMD.

