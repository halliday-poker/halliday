"""Explicit CUDA backend; no silent CPU fallback."""

import torch


class Compute:
    def __init__(self, device="cuda", seed=20261003, *, batch_size=None, memory_limit_mib=None):
        if device.startswith("cuda") and not torch.cuda.is_available():
            raise RuntimeError("CUDA is required. Install a CUDA-enabled PyTorch build; no CPU fallback was used.")
        self.device = torch.device(device)
        if batch_size is not None and batch_size < 1:
            raise ValueError("batch_size must be positive")
        self.batch_size = batch_size
        self.memory_limit_mib = memory_limit_mib
        self.dtype = torch.float64
        self.seed = int(seed)
        if memory_limit_mib is not None:
            if self.device.type != "cuda" or memory_limit_mib <= 0:
                raise ValueError("memory_limit_mib requires CUDA and a positive limit")
            total = torch.cuda.get_device_properties(self.device).total_memory
            torch.cuda.set_per_process_memory_fraction(min(1., memory_limit_mib * 2**20 / total), self.device)
        self.generator = torch.Generator(device=self.device).manual_seed(seed)
        if self.device.type == "cuda":
            torch.backends.cuda.matmul.allow_tf32 = False
            # Execute and synchronize a real kernel, not just device discovery.
            probe = torch.ones((8, 8), dtype=self.dtype, device=self.device)
            assert float((probe @ probe)[0, 0]) == 8
            torch.cuda.synchronize(self.device)

    def array(self, values, dtype=None):
        return torch.as_tensor(values, dtype=dtype or self.dtype, device=self.device)

    def zeros(self, *shape):
        return torch.zeros(shape, dtype=self.dtype, device=self.device)

    def bootstrap_weights(self, selected, total, draws):
        """Row zero is the estimate; subsequent rows resample whole matches."""
        indices = self.array(selected, torch.long)
        weights = self.zeros(draws + 1, total)
        weights[0, indices] = 1
        if draws and len(indices):
            sampled = indices[torch.randint(len(indices), (draws, len(indices)),
                                            generator=self.generator, device=self.device)]
            weights[1:].scatter_add_(1, sampled, torch.ones_like(sampled, dtype=self.dtype))
        return weights

    def metadata(self):
        return dict(device=str(self.device), seed=self.seed, torch_version=torch.__version__,
                    cuda_runtime=torch.version.cuda, dtype=str(self.dtype),
                    gpu=torch.cuda.get_device_name(self.device) if self.device.type == "cuda" else None,
                    peak_allocated_bytes=torch.cuda.max_memory_allocated(self.device) if self.device.type == "cuda" else None,
                    peak_reserved_bytes=torch.cuda.max_memory_reserved(self.device) if self.device.type == "cuda" else None,
                    batch_size=self.batch_size, memory_limit_mib=self.memory_limit_mib)
