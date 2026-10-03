# One endpoint: FLUX.2 Klein and FaceFusion

The existing `runpod-worker-docker-test` Docker build keeps ComfyUI 5.10.0 and
its four verified FLUX model files. It adds a separate FaceFusion 3.9 virtual
environment. `/start.sh` still starts ComfyUI; `/multi_handler.py` chooses the
operation from `input.mode`. The endpoint ID remains `3f5wsrqjwsixf5` when the
new GitHub build is selected by RunPod.

## Modes

- `flux`: pass `input.workflow` (the 8-step API graph in
  `flux-headswap-api.json`) and `input.images` with files named `target.png`
  and `donor.jpg` or `donor.png`. The target PNG alpha channel is the mask.
  The original ComfyUI handler returns `output.images`.
- `facefusion_photo`: pass `input.source_image` and `input.target_media` as
  base64 data URIs. Returns `output.images` and `output.output_bytes`.
- `facefusion_video`: use a face image and an MP4 target in those same two
  fields. Returns `output.videos`, `output.frame_count`, and
  `output.output_bytes`.

Example request shape:

```json
{"input":{"mode":"facefusion_photo","source_image":"data:image/jpeg;base64,...","target_media":"data:image/jpeg;base64,..."}}
```

Use `/run` then `/status/{job_id}`. The local `tester.html` embeds the FLUX API
graph and supplies the mode; it keeps the RunPod API key in browser localStorage
and never writes it into the file.

## Current video transfer limit

FaceFusion processes every frame; the local `trim_frame_end=111` was removed
for the server. `ffprobe` counts frames in the finished file and reports the
number. Until an S3-compatible bucket is connected, the combined raw input
must be at most 7 MiB and the finished video at most 5 MiB to fit comfortably
inside RunPod's `/run` JSON request and inline response. A larger completed
video returns `output_too_large_bucket_required` with its byte and frame count;
the temporary worker file is then removed. Use a short compressed MP4 for the
first video smoke test. RunPod documents a 10 MB `/run` request size in the
[worker README](https://github.com/runpod-workers/worker-comfyui/blob/5.10.0/README.md).

## FaceFusion provenance

The container clones FaceFusion commit
`358f169e95e2b02431722cc287db8acda6658df1`, the exact local checkout.
`facefusion-local.patch` carries the two local code changes the user approved.
`facefusion.ini` carries the user's settings, with DirectML replaced by CUDA
for RunPod's Linux NVIDIA GPUs and the video frame limit cleared. ONNX model
bytes are downloaded from FaceFusion's own release/Hugging Face assets during
the image build and verified against the exact sizes and CRC32 hashes observed
in the user's local installation. No model weights or credentials are in Git.

FaceFusion is distributed under OpenRAIL-AS. Individual model licenses can
impose additional conditions; review those before commercial use.
