import importlib.util
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]

def module(path, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result

class IsolatedRuntimeTests(unittest.TestCase):
    def test_private_cuda_directories_do_not_use_a_system_toolkit(self):
        worker = module("runtime/llama_worker.py", "hymt_worker_test")
        with tempfile.TemporaryDirectory() as folder:
            site = Path(folder)
            for package in ("cuda_runtime", "cublas", "cuda_nvrtc"):
                (site / "nvidia" / package / "bin").mkdir(parents=True)
            with patch.dict(os.environ), patch.object(worker.sysconfig, "get_path", return_value=folder), patch.object(worker.os, "add_dll_directory", create=True) as add:
                handles = worker.cuda_directories()
                self.assertEqual(len(handles), 3)
                self.assertEqual([Path(call.args[0]) for call in add.call_args_list], [site / "nvidia" / name / "bin" for name in ("cuda_runtime", "cublas", "cuda_nvrtc")])
                handles[0].close.assert_not_called()
            (site / "nvidia" / "cublas" / "bin").rmdir()
            with patch.object(worker.sysconfig, "get_path", return_value=folder), patch.object(worker.os, "add_dll_directory", create=True):
                with self.assertRaisesRegex(RuntimeError, "private CUDA runtime is missing"):
                    worker.cuda_directories()

    def test_launcher_removes_foreign_python_and_llama_environment(self):
        proxy = module("py/isolated_llama.py", "hymt_proxy_test")
        with tempfile.TemporaryDirectory(prefix="Hy MT2 경로 ") as folder:
            node = Path(folder)
            (node / ".venv" / "Scripts").mkdir(parents=True)
            (node / ".venv" / "Scripts" / "python.exe").touch()
            process = MagicMock()
            process.stdout = io.StringIO("")
            process.stdin = io.StringIO()
            process.poll.return_value = 0
            keys = ("PYTHONHOME", "PYTHONPATH", "CUDA_PATH", "CUDA_HOME", "HIP_PATH", "VULKAN_SDK", "LLAMA_CPP_LIB")
            with patch.object(proxy, "__file__", str(node / "py" / "isolated_llama.py")), patch.dict(os.environ, {key: "foreign" for key in keys}), patch.object(proxy.subprocess, "Popen", return_value=process) as launch, patch.object(proxy.Llama, "_request"):
                instance = proxy.Llama(model_path="test.gguf")
                args, kwargs = launch.call_args
                self.assertEqual(Path(args[0][0]), node / ".venv" / "Scripts" / "python.exe")
                self.assertIn("-I", args[0])
                self.assertTrue(all(key not in kwargs["env"] for key in keys))
                instance.close()

if __name__ == "__main__":
    unittest.main()
