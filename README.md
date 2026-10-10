# ComfyUI-Hy-MT2

## Windows portable fork

This fork runs llama-cpp-python in the node's private Python process. Its GGUF
node IDs and inputs remain compatible with the upstream node and PhotoCraft.
ComfyUI's own llama-cpp-python, Torch and other inference packages are not replaced.

1. Download **both** [install-comfyui-hymt2.cmd](https://raw.githubusercontent.com/david419kr/ComfyUI-Hy-MT2/main/install-comfyui-hymt2.cmd)
   and [install-comfyui-hymt2.ps1](https://raw.githubusercontent.com/david419kr/ComfyUI-Hy-MT2/main/install-comfyui-hymt2.ps1).
2. Put them **inside `ComfyUI_windows_portable`**, beside `ComfyUI` and
   `python_embeded`. Close ComfyUI, then double-click the CMD file.
3. Restart ComfyUI. Place GGUF translation models under `ComfyUI/models/LLM/GGUF`.

The installer detects the portable root by structure, downloads a private `uv`
tool when needed, extracts a checksum-verified Python 3.13.12 archive into the
node's `.python` using ordinary files/directories, creates `.venv`,
and installs pinned CUDA 12.8 llama-cpp-python and NVIDIA runtime/cuBLAS wheels.
No preinstalled system Python, uv, CUDA Toolkit, C++ compiler or Git is required.
With Git it clones/updates this fork; without Git it installs the GitHub ZIP.
Requirements: Windows x64, a working NVIDIA ComfyUI portable installation with
a CUDA 12.8-compatible driver, network access and several GB of free disk space.
GGUF models are separate; this installer does not download model weights.

Existing upstream/ZIP nodes are backed up outside `custom_nodes`, in
`.hymt2-backups`, so ComfyUI does not load them twice. An existing clean Git fork
updates with fast-forward only; locally edited sources are preserved and require
manual reconciliation. Runtime files are ignored by Git. Rerun the installer
after moving the portable folder to repair/recreate a broken private environment.
Backups are retained until you remove them yourself. No global PATH or CUDA
installation is changed. The installer checks CUDA backend loading without
loading a model. A missing host huggingface-hub dependency is installed into the
embedded ComfyUI Python; the llama runtime stays isolated.

For a portable folder elsewhere, run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install-comfyui-hymt2.ps1 -PortableRoot "E:\AI\ComfyUI_windows_portable"
```

The original node's features and model documentation follow below. This fork
retains the original GPL-3.0 license. The original registry publishing workflow
is restricted to the upstream repository.

PhotoCraft detects these local translation files automatically:

- `Hy-MT2-1.8B-heretic.i1-Q4_K_M.gguf`
- `HY-MT2-7B-Abliterated-Q4_K_M.gguf`

The newly authored installer/private-worker files carry MIT SPDX headers; the
upstream node and the remainder of this fork retain GPL-3.0.

Verified on 2026-10-11 with Windows PowerShell 5.1: fresh installation in a
path containing spaces and Korean characters, Git fast-forward update, Git-free
ZIP installation with source backup and environment reuse, and CUDA loading
without system Toolkit paths. The installed node translated a short Korean
greeting to English using the 1.8B Heretic model and then unloaded its worker.
This was tested on one NVIDIA PC; other hardware has not been tested.

If an older installer stopped at `Failed to create Python minor version link
directory`, replace the root `install-comfyui-hymt2.ps1` with the latest download
and run the CMD again. The new installer does not use `uv python install` or
minor-version junctions. It reuses a valid patch-version Python already extracted
by the failed installation and passes that real executable directly to venv.
No node or Python directory needs to be deleted. This supports installation
locations where version links cannot be created; the actual filesystem of a
reported failing friend PC was not inspected. Windows PowerShell 5.1 regression
checks verified fresh archive extraction/venv creation with zero reparse points
and failed-install Python reuse without another download.

[![HuggingFace](https://img.shields.io/badge/%F0%9F%A4%97%20Hugging%20Face-Tencent%20Hy--MT2-ffc107?color=ffc107&logoColor=white)](https://huggingface.co/collections/tencent/hy-mt2)
[![ModelScope](https://img.shields.io/badge/ModelScope-Tencent%20Hy--MT2-624aff)](https://modelscope.cn/collections/Tencent-Hunyuan/Hy-MT2)
[![GitHub](https://img.shields.io/badge/GitHub-Tencent--Hunyuan%2FHy--MT2-black?logo=github)](https://github.com/Tencent-Hunyuan/Hy-MT2)

A lightweight, fast, and memory-efficient ComfyUI translation node designed for Tencent **Hy-MT2** GGUF models.

---

## Features

- **Lightweight & Low VRAM**: Powered by GGUF (`llama-cpp-python`). The 1.8B Q4 model uses only ~1.1 GB VRAM, avoiding memory contention with diffusion models.
- **Smart Dual-Direction Auto Detection**: Default `Auto (Chinese ⇋ English)` automatically translates Chinese text to English and English to Chinese without manual intervention.
- **Full Official Language Coverage**: All 38 languages and regional dialects officially supported by Tencent Hy-MT2 (Chinese, English, French, Portuguese, Spanish, Japanese, Turkish, Russian, Arabic, Korean, Thai, Italian, German, Vietnamese, Malay, Indonesian, Filipino, Hindi, Traditional Chinese, Polish, Czech, Dutch, Khmer, Burmese, Persian, Gujarati, Urdu, Telugu, Marathi, Hebrew, Bengali, Tamil, Ukrainian, Tibetan, Kazakh, Mongolian, Uyghur, Cantonese).
- **Prompt & Cinematics Syntax Protection**: Automatically shields `<lora:...>`, `<Picture n>`, character dialogues (`<d>[Language] "..."</d>`), shot headers (`[Shot ...]`), and `__wildcards__` from translation distortion while preserving full translation for weighted tags like `(red dress:1.2)` and `[red dress]`.
- **Dual-Channel Auto Download**: Automatically downloads `.gguf` models directly to `models/LLM/GGUF`. Seamlessly falls back to ModelScope CDN if Hugging Face is unreachable.
- **14 Built-in Translation Styles**: Rich stylistic guidance including AI Prompt/Visual Tags, Anime & ACG, Cinematic Arts, Literary, and Subtitles.
- **Output Sanitization**: Strips `<think>` tags, leaked tokens, and code block formatting.

---

## Node Reference

### `Hy-MT2 Translate (GGUF)` / `(GGUF Pro)`
- **Category**: `🧪AILab/🌍Translate`
- **Inputs**:
  - `model`: Official preset or local `.gguf` file.
    - `Hy-MT2-1.8B-Q4_K_M.gguf (1.1 GB)` (Fast & lowest VRAM, default)
    - `Hy-MT2-7B-Q4_K_M.gguf (4.5 GB)` (Balanced 7B quality)
    - `Hy-MT2-1.8B-Q6_K.gguf (1.5 GB)` (Near-lossless 1.8B)
    - `Hy-MT2-7B-Q6_K.gguf (5.9 GB)` (Near-lossless 7B)
    - `Hy-MT2-1.8B-Q8_0.gguf (1.9 GB)` (Maximum precision 1.8B)
    - `Hy-MT2-7B-Q8_0.gguf (7.5 GB)` (Maximum precision 7B)
  - `translate_style`: Stylistic constraint (`Default`, `AI Prompt / Visual Tags`, `Daily Conversational`, `Formal Business`, `Literary & Novel`, `Anime & ACG`, `Cinematic & Visual Arts`, `Scholarly & Academic`, `Popular Science`, `Marketing Copy`, `News & Media`, `Video Subtitles`, `Legal & Contract`, `Ancient / Poetic`). Default is `Default`.
  - `translate_to`: `Auto` (default) or one of the 38 supported languages.
  - `text`: Text or prompt to translate (multiline input with placeholder).
  - `unload_after_run`: Unload model from VRAM after translation (default: `False`).
- **Pro Version Features**:
  - Automatic prompt syntax masking: shields `<lora:...>`, embedding tags, and `(weight:1.2)` values from translation distortion.
  - Automatic comma/spacing formatting normalization for prompt workflows.
  - In-node translation preview & word/character count metrics.
- **Outputs**:
  - `text`: Translated output string.

---

## Model Comparison & Selection Guide

| Model Preset | Params | Quant | File Size | Approx. VRAM | Quality / Fidelity | Recommended Use Case |
|---|---|---|---|---|---|---|
| **Hy-MT2-1.8B-Q4_K_M.gguf** *(Default)* | 1.8B | Q4_K_M | **~1.1 GB** | ~1.4 GB | ⭐⭐⭐⭐ (Fast & Solid) | Everyday prompt translation; minimal VRAM footprint alongside SDXL/Flux |
| **Hy-MT2-1.8B-Q6_K.gguf** | 1.8B | Q6_K | **~1.5 GB** | ~1.8 GB | ⭐⭐⭐⭐⭐ (Near-Lossless 1.8B) | Low-VRAM setups desiring higher translation precision & nuances |
| **Hy-MT2-1.8B-Q8_0.gguf** | 1.8B | Q8_0 | **~1.9 GB** | ~2.2 GB | ⭐⭐⭐⭐⭐ (Full 8-bit 1.8B) | Maximum precision baseline for 1.8B parameter scale |
| **Hy-MT2-7B-Q4_K_M.gguf** | 7B | Q4_K_M | **~4.5 GB** | ~5.0 GB | ⭐⭐⭐⭐⭐ (Strong 7B Quality) | Complex domain, long paragraphs, or challenging literary texts |
| **Hy-MT2-7B-Q6_K.gguf** | 7B | Q6_K | **~5.9 GB** | ~6.4 GB | ⭐⭐⭐⭐⭐+ (Near-Lossless 7B) | Optimal sweet spot for 12GB+ GPUs seeking top-tier translation |
| **Hy-MT2-7B-Q8_0.gguf** | 7B | Q8_0 | **~7.5 GB** | ~8.0 GB | ⭐⭐⭐⭐⭐+ (Pure 8-bit 7B) | Dedicated translation tasks with 16GB+ VRAM or CPU offload |
| *Hy-MT2-1.8B-2bit-GGUF*\* | 1.8B | 2-bit STQ | ~600 MB | ~0.8 GB | ⭐⭐⭐ (Compressed) | Mobile / edge testing *(Requires custom llama.cpp)* |
| *Hy-MT2-1.8B-1.25bit-GGUF*\* | 1.8B | 1.25-bit STQ | ~440 MB | ~0.6 GB | ⭐⭐⭐ (Extreme) | Extreme edge deployment *(Requires custom llama.cpp)* |

*\*Note: 1.25-bit and 2-bit models are not built into the preset dropdown because they depend on Tencent's custom STQ kernel.*

---

## Model Quantization Notes

### Why are 1.25-bit and 2-bit GGUF models not in the default presets?
Tencent released extreme quantization models ([`Hy-MT2-1.8B-1.25bit-GGUF`](https://huggingface.co/tencent/Hy-MT2-1.8B-1.25bit-GGUF) and [`Hy-MT2-1.8B-2bit-GGUF`](https://huggingface.co/tencent/Hy-MT2-1.8B-2bit-GGUF)) based on the **AngelSlim STQ (Sparse Ternary Quantization / Sherry)** algorithm.
- **Custom Kernel Dependency**: These extreme quantizations require a dedicated `STQ_0` / `STQ1_0` computation kernel, introduced via [llama.cpp PR #22836](https://github.com/ggml-org/llama.cpp/pull/22836).
- **Standard Pre-built Binaries**: Standard pre-built wheels of `llama-cpp-python` (used by ComfyUI) do **not** bundle this custom kernel and will throw tensor decoding errors.
- **How to use them**: Advanced users who compile `llama.cpp` / `llama-cpp-python` from source with PR #22836 can manually download the `.gguf` file into `models/LLM/GGUF`. The node will automatically detect and load it from the local file scanner.

---

## Dependencies

```bash
# Host dependency only; the Windows installer manages the private llama runtime.
pip install huggingface-hub
```

---

If this custom node helps you or you like my work, please give me ⭐ on this repo! It's a great encouragement for my efforts!

## License
GPL-3.0 License
