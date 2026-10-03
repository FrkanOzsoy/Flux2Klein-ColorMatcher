"""Bake the exact FaceFusion model files present in the local 3.9 checkout.

Sizes and CRC32 values were read from the local FaceFusion model directory. The source
code chooses these release tags. No model bytes are stored in Git.
"""

from pathlib import Path
from urllib.request import urlopen
import time
import zlib

DEST = Path("/opt/facefusion/.assets/models")
DEST.mkdir(parents=True, exist_ok=True)

# filename stem: (FaceFusion asset release, exact local bytes, local CRC32)
MODELS = {
    "hyperswap_1c_256": ("models-3.3.0", 402742682, "83c5ce36"),
    "gpen_bfr_512": ("models-3.0.0", 284340240, "30505711"),
    "yoloface_8n": ("models-3.0.0", 12659761, "f9a0382f"),
    "2dfan4": ("models-3.0.0", 97904803, "a948738e"),
    "xseg_3": ("models-3.2.0", 70327709, "e99b694c"),
    "bisenet_resnet_34": ("models-3.0.0", 93632546, "35d17a50"),
    "arcface_w600k_r50": ("models-3.0.0", 174388474, "1f5fefb8"),
    "nsfw_1": ("models-3.3.0", 80414194, "f602d1c5"),
    "nsfw_2": ("models-3.3.0", 22489928, "c7fa5fe2"),
    "nsfw_3": ("models-3.3.0", 358188033, "633a3b02"),
    "fairface": ("models-3.0.0", 85170772, "10d79769"),
}


def verify(path: Path, size: int, crc: str) -> bool:
    if not path.is_file() or path.stat().st_size != size:
        return False
    value = 0
    with path.open("rb") as source:
        while chunk := source.read(8 * 1024 * 1024):
            value = zlib.crc32(chunk, value)
    return f"{value:08x}" == crc


for name, (release, size, crc) in MODELS.items():
    path = DEST / f"{name}.onnx"
    if not verify(path, size, crc):
        url = f"https://huggingface.co/facefusion/{release}/resolve/main/{name}.onnx"
        for attempt in range(3):
            try:
                print(f"Downloading {name} from {url} (attempt {attempt + 1})", flush=True)
                with urlopen(url, timeout=90) as source, path.open("wb") as target:
                    while chunk := source.read(8 * 1024 * 1024):
                        target.write(chunk)
                if verify(path, size, crc):
                    break
                print(f"Size/CRC mismatch for {name}", flush=True)
            except Exception as exc:
                print(f"Download failed for {name}: {exc}", flush=True)
            if verify(path, size, crc):
                break
            time.sleep(5)
        if not verify(path, size, crc):
            raise SystemExit(f"FaceFusion model {name} could not be verified")
    (DEST / f"{name}.hash").write_text(crc, encoding="ascii")
    print(f"OK {name}: {size} bytes, CRC32 {crc}", flush=True)

