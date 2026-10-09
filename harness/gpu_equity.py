"""Optional CUDA hand ranking for offline equity simulations.

Uses the CUDA driver API and nvcc; no CUDA Python package is required. Native
cubins avoid depending on the driver's PTX compiler. Only workers make contexts.
Range sampling and weighted aggregation remain in bot/engine.py.
"""

import ctypes as C
from ctypes.util import find_library
from hashlib import sha256
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from time import perf_counter


class CudaError(RuntimeError):
    pass


class Driver:
    def __init__(self):
        self.lib = C.CDLL(find_library("cuda") or ("nvcuda.dll" if os.name == "nt" else "libcuda.so.1"))
        ptr, integer, size = C.c_void_p, C.c_int, C.c_size_t
        signatures = {
            "cuInit": [C.c_uint], "cuDeviceGetCount": [C.POINTER(integer)],
            "cuDeviceGet": [C.POINTER(integer), integer],
            "cuDeviceGetName": [ptr, integer, integer],
            "cuDeviceGetAttribute": [C.POINTER(integer), integer, integer],
            "cuCtxCreate_v2": [C.POINTER(ptr), C.c_uint, integer],
            "cuCtxDestroy_v2": [ptr],
            "cuModuleLoad": [C.POINTER(ptr), C.c_char_p],
            "cuModuleGetFunction": [C.POINTER(ptr), ptr, C.c_char_p],
            "cuMemAlloc_v2": [C.POINTER(C.c_uint64), size],
            "cuMemcpyHtoD_v2": [C.c_uint64, ptr, size],
            "cuMemcpyDtoH_v2": [ptr, C.c_uint64, size],
            "cuLaunchKernel": [ptr, C.c_uint, C.c_uint, C.c_uint,
                               C.c_uint, C.c_uint, C.c_uint, C.c_uint,
                               ptr, C.POINTER(ptr), C.POINTER(ptr)],
            "cuGetErrorName": [integer, C.POINTER(C.c_char_p)],
            "cuGetErrorString": [integer, C.POINTER(C.c_char_p)],
        }
        for name, args in signatures.items():
            function = getattr(self.lib, name)
            function.argtypes, function.restype = args, integer
        self.call("cuInit", 0)

    def call(self, name, *args):
        result = getattr(self.lib, name)(*args)
        if result:
            code, message = C.c_char_p(), C.c_char_p()
            self.lib.cuGetErrorName(result, C.byref(code))
            self.lib.cuGetErrorString(result, C.byref(message))
            detail = (message.value or code.value or b"unknown error").decode()
            raise CudaError(f"{name}: {detail} (CUDA error {result})")

    def devices(self):
        count = C.c_int()
        self.call("cuDeviceGetCount", C.byref(count))
        result = []
        for ordinal in range(count.value):
            device, major, minor = C.c_int(), C.c_int(), C.c_int()
            self.call("cuDeviceGet", C.byref(device), ordinal)
            name = C.create_string_buffer(256)
            self.call("cuDeviceGetName", name, len(name), device)
            self.call("cuDeviceGetAttribute", C.byref(major), 75, device)
            self.call("cuDeviceGetAttribute", C.byref(minor), 76, device)
            result.append(dict(index=ordinal, name=name.value.decode(),
                               architecture=f"sm_{major.value}{minor.value}"))
        return result


def find_nvcc():
    found = shutil.which("nvcc")
    if found:
        return found
    for root in (os.environ.get("CUDA_PATH"), "/usr/local/cuda"):
        if root:
            path = Path(root) / "bin" / ("nvcc.exe" if os.name == "nt" else "nvcc")
            if path.is_file():
                return str(path)
    raise CudaError("nvcc not found; install a CUDA toolkit or add its bin directory to PATH")


def compiled_kernel(architecture):
    nvcc = find_nvcc()
    source = Path(__file__).with_name("gpu_rank.cu")
    version = subprocess.check_output([nvcc, "--version"], timeout=15)
    digest = sha256(source.read_bytes() + architecture.encode() + version).hexdigest()[:20]
    cache = source.parent / "results" / "cuda-cache"
    cache.mkdir(parents=True, exist_ok=True)
    binary = cache / f"rank-{architecture}-{digest}.cubin"
    if binary.exists():
        return binary
    with tempfile.TemporaryDirectory(dir=cache) as temp:
        output = Path(temp) / "rank.cubin"
        process = subprocess.run([nvcc, "--cubin", f"-arch={architecture}", "-O3",
                                  str(source), "-o", str(output)],
                                 capture_output=True, text=True, timeout=90)
        if process.returncode:
            raise CudaError(f"CUDA kernel compilation failed: {process.stderr.strip()}")
        output.replace(binary)
    return binary


class CudaEvaluator:
    def __init__(self, device, batch_size=128):
        import numpy as np
        if not 1 <= batch_size <= 4096:
            raise ValueError("GPU batch size must be between 1 and 4096")
        self.driver = Driver()
        info = next((d for d in self.driver.devices() if d["index"] == device), None)
        if info is None:
            raise CudaError(f"CUDA device {device} is not available")
        binary = compiled_kernel(info["architecture"])
        self.device, self.name, self.batch_size = device, info["name"], batch_size
        self.capacity = batch_size * 9
        self.context = C.c_void_p()
        self.driver.call("cuCtxCreate_v2", C.byref(self.context), 0, device)
        try:
            self.module, self.function = C.c_void_p(), C.c_void_p()
            self.driver.call("cuModuleLoad", C.byref(self.module), os.fsencode(binary))
            self.driver.call("cuModuleGetFunction", C.byref(self.function), self.module, b"rank_hands")
            self.cards, self.ranks = C.c_uint64(), C.c_uint64()
            self.buffer_bytes = self.capacity * 8 * 4
            self.driver.call("cuMemAlloc_v2", C.byref(self.cards), self.capacity * 7 * 4)
            self.driver.call("cuMemAlloc_v2", C.byref(self.ranks), self.capacity * 4)
            self.host_ranks = np.empty(self.capacity, dtype=np.int32)
            self.batches = self.hands = 0
            self.seconds = 0.0
            if self.evaluate([(8, 9, 10, 11, 12, 13, 14)]) != [(8, 14)]:
                raise CudaError("CUDA hand-ranking startup probe failed")
            self.batches = self.hands = 0
            self.seconds = 0.0
        except BaseException:
            self.close()
            raise

    def evaluate(self, hands):
        import numpy as np
        result = []
        lengths = (5, 4, 3, 3, 1, 5, 2, 2, 1)
        for start in range(0, len(hands), self.capacity):
            chunk = np.ascontiguousarray(hands[start:start + self.capacity], dtype=np.int32)
            if chunk.shape != (len(chunk), 7):
                raise ValueError("CUDA evaluator requires seven cards per hand")
            if chunk.min() < 0 or chunk.max() >= 52:
                raise ValueError("CUDA card IDs must be between 0 and 51")
            began = perf_counter()
            count = C.c_int(len(chunk))
            self.driver.call("cuMemcpyHtoD_v2", self.cards, chunk.ctypes.data, chunk.nbytes)
            args = (C.c_void_p * 3)(C.addressof(self.cards), C.addressof(self.ranks), C.addressof(count))
            self.driver.call("cuLaunchKernel", self.function, (count.value + 127) // 128, 1, 1,
                             128, 1, 1, 0, None, args, None)
            self.driver.call("cuMemcpyDtoH_v2", self.host_ranks.ctypes.data, self.ranks, count.value * 4)
            self.seconds += perf_counter() - began
            self.batches += 1
            self.hands += count.value
            for raw in self.host_ranks[:count.value]:
                value = int(raw)
                category = value >> 20
                result.append((category, *(value >> (16 - 4 * i) & 15
                                           for i in range(lengths[category]))))
        return result

    def metadata(self):
        return dict(device=f"cuda:{self.device}", gpu=self.name,
                    batches=self.batches, ranked_hands=self.hands,
                    gpu_seconds=self.seconds, batch_size=self.batch_size,
                    device_buffer_bytes=self.buffer_bytes)

    def close(self):
        if self.context:
            self.driver.call("cuCtxDestroy_v2", self.context)
            self.context = C.c_void_p()
