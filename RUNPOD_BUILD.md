# RunPod worker Docker test

This branch adds a Dockerfile for the existing public Flux2Klein-ColorMatcher node pack. It uses the official `runpod/worker-comfyui:5.10.0-base` image and installs the public custom-node dependencies for the user's workflow. The two in-house node classes are checked during the build.

## Build test

```bash
docker build --platform linux/amd64 -t flux2klein-colormatcher:test .
```

The build imports the custom pack, asserts that `PhotoColorGrainMatch` and `Flux2KleinColorAnchor` register, and runs ComfyUI's CPU startup check. This does not run image inference.

## RunPod setup after review

RunPod Serverless > New Endpoint > Start from GitHub Repo:
- Repository: `FrkanOzsoy/Flux2Klein-ColorMatcher`
- Branch: `runpod-worker-docker-test`
- Context Path: `/`
- Dockerfile Path: `Dockerfile`

Supply model weights separately through a network volume. The workflow editor JSON is intentionally not in this public repository; export it from ComfyUI with **Workflow > Export (API)** for the worker request. The API input uses `input.workflow` and optional `input.images`.

This branch is a build candidate only. No RunPod endpoint or GPU worker is created by these files.
## Current workflow inputs and model paths

The current editor workflow has **two** LoadImage nodes and is not yet the requested three-photo API. Keep the API contract pending until the role of the third photo is specified. The base image's network-volume mapping expects the GGUF diffusion model in `/runpod-volume/models/unet/`, the GGUF text encoder in `/runpod-volume/models/clip/`, the VAE in `/runpod-volume/models/vae/`, and the LoRA in `/runpod-volume/models/loras/`.
