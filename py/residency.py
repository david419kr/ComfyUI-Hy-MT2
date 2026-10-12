# SPDX-License-Identifier: MIT
"""Keep the private translator across workflows, with ComfyUI pressure eviction."""
import atexit
import copy
import functools
import logging
import threading
from contextlib import contextmanager
from pathlib import Path

from .isolated_llama import Llama

LOG = logging.getLogger(__name__)
GIB = 1024 ** 3


class ResidentTranslator:
    def __init__(self):
        self.lock = threading.RLock()
        self.llm = None
        self.signature = None
        self.device = None
        self.busy = False

    @contextmanager
    def session(self):
        with self.lock:
            self.busy = True
            try:
                yield
            finally:
                self.busy = False

    def acquire(self, model_path, gpu_layers=-1):
        signature = (str(Path(model_path).resolve()), int(gpu_layers))
        if self.signature == signature and self.llm is not None and self.llm.is_alive():
            LOG.info("[HyMT residency] Reusing translation worker")
            return self.llm
        self.release("model change or worker exit")
        if gpu_layers != 0:
            import comfy.model_management as mm
            self.device = mm.get_torch_device()
            # Include KV/work buffers; release only the deficit, never all image models.
            if self.device.type == "cuda":
                required = Path(model_path).stat().st_size + GIB
                if mm.get_free_memory(self.device) < required:
                    LOG.info("[HyMT residency] Making room for translation: %.0f MB", required / 1024 ** 2)
                    mm.free_memory(required, self.device)
                # An external CUDA process cannot use PyTorch's unused reserved pages.
                if mm.torch.cuda.mem_get_info(self.device)[0] < required:
                    mm.soft_empty_cache()
        llm = Llama(model_path=str(model_path), n_gpu_layers=int(gpu_layers), n_ctx=8192, verbose=False)
        self.llm = llm
        self.signature = signature
        LOG.info("[HyMT residency] Translation worker loaded")
        return llm

    def release(self, reason):
        with self.lock:
            if self.llm is not None:
                self.llm.close()
                LOG.info("[HyMT residency] Translation worker unloaded: %s", reason)
            self.llm = None
            self.signature = None
            self.device = None

    def release_for_pressure(self, required, device, mm, dynamic=False):
        if not self.lock.acquire(blocking=False):
            return
        try:
            if self.llm is None or self.busy or device != self.device:
                return
            # DynamicVRAM requests virtual model sizes; evict only for real headroom loss.
            target = min(required, mm.minimum_inference_memory()) if dynamic else required
            if mm.get_free_memory(device) < target:
                self.release("VRAM pressure or explicit unload")
        finally:
            self.lock.release()


TRANSLATOR = ResidentTranslator()
atexit.register(TRANSLATOR.release, "ComfyUI exit")


class ImageLoaderKeepalive:
    """Unused loader nodes retain cache keys without executing image inference."""
    def __init__(self):
        self.loaders = {}

    def clear(self):
        self.loaders.clear()

    def __call__(self, data):
        prompt = data.get("prompt", {})
        if not isinstance(prompt, dict):
            return data
        kinds = {node.get("class_type") for node in prompt.values() if isinstance(node, dict)}
        if "HyMT_Translation_GGUF" in kinds and kinds <= {"HyMT_Translation_GGUF", "PreviewAny"}:
            for key, node in self.loaders.items():
                prompt.setdefault(key, copy.deepcopy(node))
            if self.loaders:
                LOG.info("[HyMT residency] Preserving %d image loader cache keys during translation", len(self.loaders))
        else:
            loaders = {
                key: copy.deepcopy(node) for key, node in prompt.items()
                if isinstance(node, dict) and node.get("class_type") in {"UNETLoader", "CLIPLoader", "VAELoader"}
                and isinstance(node.get("inputs"), dict)
                and all(not isinstance(value, (list, dict)) for value in node["inputs"].values())
            }
            if loaders:
                self.loaders = loaders
        return data


def install():
    import comfy.model_management as mm
    from server import PromptServer

    if getattr(mm.free_memory, "_hymt_residency", False):
        return
    original = mm.free_memory
    original_unload = mm.unload_all_models
    keepalive = ImageLoaderKeepalive()

    @functools.wraps(original)
    def free_memory(memory_required, device, *args, **kwargs):
        dynamic = kwargs.get("for_dynamic", args[1] if len(args) > 1 else False)
        TRANSLATOR.release_for_pressure(memory_required, device, mm, dynamic)
        return original(memory_required, device, *args, **kwargs)

    free_memory._hymt_residency = True
    mm.free_memory = free_memory

    @functools.wraps(original_unload)
    def unload_all_models(*args, **kwargs):
        TRANSLATOR.release("explicit unload")
        keepalive.clear()
        return original_unload(*args, **kwargs)

    mm.unload_all_models = unload_all_models
    PromptServer.instance.add_on_prompt_handler(keepalive)
    LOG.info("[HyMT residency] Persistent translation and image loader keepalive enabled")
