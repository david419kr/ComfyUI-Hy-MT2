# SPDX-License-Identifier: MIT
"""Private stdin/stdout worker; runs only in the Hy-MT2 node's dedicated venv."""
import contextlib
import json
import os
import sys
import sysconfig
import traceback
from pathlib import Path

def cuda_directories():
    """Keep DLL-directory handles alive while the private CUDA backend is in use."""
    if os.name != "nt":
        return []
    handles = []
    site = Path(sysconfig.get_path("purelib"))
    paths = []
    for package in ("cuda_runtime", "cublas", "cuda_nvrtc"):
        directory = site / "nvidia" / package / "bin"
        if not directory.is_dir():
            raise RuntimeError("Hy-MT2 private CUDA runtime is missing; rerun install-comfyui-hymt2.cmd")
        handles.append(os.add_dll_directory(str(directory)))
        paths.append(str(directory))
    os.environ["PATH"] = os.pathsep.join(paths + [os.environ.get("PATH", "")])
    return handles

def check_runtime():
    import llama_cpp
    from llama_cpp._ggml import ggml_backend_load_all_from_path
    from llama_cpp import llama_backend_init, llama_backend_free, llama_supports_gpu_offload
    llama_backend_init()
    try:
        ggml_backend_load_all_from_path(str(Path(llama_cpp.__file__).resolve().parent / "lib").encode("utf-8"))
        supported = bool(llama_supports_gpu_offload())
        if not supported:
            raise RuntimeError("Hy-MT2 CUDA backend did not load; check the NVIDIA driver and installer output")
        print(json.dumps({"ok": True, "gpu_offload": supported, "python": sys.executable}))
    finally:
        llama_backend_free()

def main():
    for key in ("CUDA_PATH", "CUDA_HOME", "HIP_PATH", "VULKAN_SDK", "LLAMA_CPP_LIB"):
        os.environ.pop(key, None)
    directories = cuda_directories()
    if sys.argv[1:] == ["--check"]:
        check_runtime()
        return
    output = sys.stdout
    model = None
    try:
        for line in sys.stdin:
            try:
                request = json.loads(line)
                with contextlib.redirect_stdout(sys.stderr):
                    if request["op"] == "load":
                        from llama_cpp import Llama
                        args = request["args"]
                        if Path(args.get("model_path", "")).name == "Hy-MT2-1.8B-heretic.i1-Q4_K_M.gguf":
                            # This GGUF stores EOS=3 ('$'); its official tokenizer uses 120020.
                            args["kv_overrides"] = {**args.get("kv_overrides", {}), "tokenizer.ggml.eos_token_id": 120020}
                        model = Llama(**args)
                        result = None
                    elif request["op"] == "complete" and model is not None:
                        result = model.create_chat_completion(**request["args"])
                    else:
                        raise ValueError("Unknown operation or model not loaded")
                response = {"ok": True, "result": result}
            except Exception as error:
                traceback.print_exc(file=sys.stderr)
                response = {"ok": False, "error": str(error)}
            output.write(json.dumps(response, ensure_ascii=False) + "\n")
            output.flush()
    finally:
        if model is not None:
            with contextlib.redirect_stdout(sys.stderr):
                model.close()
        for directory in directories:
            directory.close()

if __name__ == "__main__":
    main()
