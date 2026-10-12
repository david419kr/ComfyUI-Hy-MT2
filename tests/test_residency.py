# SPDX-License-Identifier: MIT
import copy
import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "hymt_residency_tests"
package = types.ModuleType(PACKAGE)
package.__path__ = [str(ROOT / "py")]
sys.modules[PACKAGE] = package
spec = importlib.util.spec_from_file_location(f"{PACKAGE}.residency", ROOT / "py/residency.py")
residency = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = residency
spec.loader.exec_module(residency)


class ResidencyTests(unittest.TestCase):
    def test_worker_survives_separate_sessions_and_switch_closes_old_worker(self):
        pool = residency.ResidentTranslator()
        with patch.object(residency, "Llama") as factory:
            worker = factory.return_value
            worker.is_alive.return_value = True
            with pool.session():
                self.assertIs(pool.acquire("first.gguf", 0), worker)
            with pool.session():
                self.assertIs(pool.acquire("first.gguf", 0), worker)
            factory.assert_called_once()
            worker.close.assert_not_called()
            with pool.session():
                pool.acquire("second.gguf", 0)
            worker.close.assert_called_once()
            self.assertEqual(factory.call_count, 2)
            pool.release("explicit unload")
            self.assertIsNone(pool.llm)

    def test_pressure_evicts_only_idle_worker_on_its_device(self):
        pool = residency.ResidentTranslator()
        worker = MagicMock()
        pool.llm = worker
        pool.device = "cuda:0"
        mm = MagicMock()
        mm.get_free_memory.return_value = 8 * residency.GIB
        mm.minimum_inference_memory.return_value = residency.GIB
        pool.release_for_pressure(4 * residency.GIB, "cuda:0", mm)
        # Virtual sizes in DynamicVRAM must not force an otherwise needless eviction.
        pool.release_for_pressure(32 * residency.GIB, "cuda:0", mm, dynamic=True)
        mm.get_free_memory.return_value = 0
        pool.release_for_pressure(residency.GIB, "cuda:1", mm)
        with pool.session():
            pool.release_for_pressure(residency.GIB, "cuda:0", mm)
        worker.close.assert_not_called()
        pool.release_for_pressure(residency.GIB, "cuda:0", mm)
        worker.close.assert_called_once()

    def test_explicit_unload_releases_even_with_plenty_of_free_vram(self):
        pool = residency.ResidentTranslator()
        pool.llm = MagicMock()
        worker = pool.llm
        pool.device = "cuda:0"
        mm = MagicMock()
        mm.get_free_memory.return_value = 20 * residency.GIB
        pool.release_for_pressure(1e30, "cuda:0", mm)
        worker.close.assert_called_once()

    def test_translation_preflight_preserves_models_when_room_exists(self):
        pool = residency.ResidentTranslator()
        mm = MagicMock()
        mm.get_torch_device.return_value = types.SimpleNamespace(type="cuda")
        mm.get_free_memory.return_value = 10 * residency.GIB
        mm.torch.cuda.mem_get_info.return_value = (10 * residency.GIB, 24 * residency.GIB)
        with tempfile.NamedTemporaryFile() as file, patch.dict(sys.modules, {"comfy": types.ModuleType("comfy"), "comfy.model_management": mm}), patch.object(residency, "Llama"):
            with pool.session():
                pool.acquire(file.name)
            mm.free_memory.assert_not_called()
            mm.soft_empty_cache.assert_not_called()
            pool.release("test")

    def test_translation_preflight_requests_a_finite_budget_only_on_shortage(self):
        pool = residency.ResidentTranslator()
        mm = MagicMock()
        mm.get_torch_device.return_value = types.SimpleNamespace(type="cuda")
        mm.get_free_memory.return_value = 0
        mm.torch.cuda.mem_get_info.return_value = (0, 24 * residency.GIB)
        with tempfile.NamedTemporaryFile() as file, patch.dict(sys.modules, {"comfy": types.ModuleType("comfy"), "comfy.model_management": mm}), patch.object(residency, "Llama"):
            with pool.session():
                pool.acquire(file.name)
            mm.free_memory.assert_called_once_with(residency.GIB, pool.device)
            mm.soft_empty_cache.assert_called_once()
            pool.release("test")

    def test_loader_keepalive_preserves_keys_and_excludes_image_outputs(self):
        hook = residency.ImageLoaderKeepalive()
        image = {"prompt": {
            "37": {"class_type": "UNETLoader", "inputs": {"unet_name": "nested/model.safetensors", "weight_dtype": "default"}},
            "38": {"class_type": "CLIPLoader", "inputs": {"clip_name": "te.safetensors", "type": "qwen_image", "device": "default"}},
            "39": {"class_type": "VAELoader", "inputs": {"vae_name": "vae.safetensors"}},
            "56": {"class_type": "SaveImage", "inputs": {"images": ["8", 0]}},
        }}
        hook(image)
        original = copy.deepcopy(image)
        translation = {"prompt": {"901": {"class_type": "HyMT_Translation_GGUF", "inputs": {}}, "902": {"class_type": "PreviewAny", "inputs": {"source": ["901", 0]}}}}
        hook(translation)
        self.assertEqual(set(translation["prompt"]), {"37", "38", "39", "901", "902"})
        self.assertEqual(translation["prompt"]["37"], original["prompt"]["37"])
        image["prompt"]["37"]["inputs"]["unet_name"] = "changed.safetensors"
        self.assertEqual(translation["prompt"]["37"]["inputs"]["unet_name"], "nested/model.safetensors")
        other = {"prompt": {"1": {"class_type": "PreviewAny", "inputs": {"source": "text"}}}}
        before = copy.deepcopy(other)
        hook(other)
        self.assertEqual(other, before)

    def test_loader_keepalive_does_not_inject_dangling_links(self):
        hook = residency.ImageLoaderKeepalive()
        hook({"prompt": {"37": {"class_type": "UNETLoader", "inputs": {"unet_name": ["36", 0]}}}})
        self.assertEqual(hook.loaders, {})

    def test_install_is_idempotent_and_preserves_keyword_memory_requests(self):
        mm = types.ModuleType("comfy.model_management")
        original = MagicMock(return_value=[])
        original._hymt_residency = False
        mm.free_memory = original
        mm.unload_all_models = MagicMock(return_value="unloaded")
        original_unload = mm.unload_all_models
        server = types.ModuleType("server")
        server.PromptServer = types.SimpleNamespace(instance=MagicMock())
        with patch.dict(sys.modules, {"comfy": types.ModuleType("comfy"), "comfy.model_management": mm, "server": server}), patch.object(residency.TRANSLATOR, "release_for_pressure") as pressure:
            residency.install()
            residency.install()
            self.assertEqual(mm.free_memory(memory_required=123, device="cuda:0", for_dynamic=True), [])
            pressure.assert_called_once_with(123, "cuda:0", mm, True)
            original.assert_called_once_with(123, "cuda:0", for_dynamic=True)
            server.PromptServer.instance.add_on_prompt_handler.assert_called_once()
            hook = server.PromptServer.instance.add_on_prompt_handler.call_args.args[0]
            hook.loaders = {"37": {"class_type": "UNETLoader", "inputs": {"unet_name": "old.safetensors"}}}
            with patch.object(residency.TRANSLATOR, "release") as release:
                self.assertEqual(mm.unload_all_models(), "unloaded")
                release.assert_called_once_with("explicit unload")
            original_unload.assert_called_once_with()
            self.assertEqual(hook.loaders, {})


if __name__ == "__main__":
    unittest.main()
