from __future__ import annotations

import ctypes
import os
from pathlib import Path

import torch


def count_parameters(model) -> int:
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


def ensure_directory(path: str | os.PathLike[str]) -> Path:
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def safe_read_text(path: str | os.PathLike[str]) -> str:
    return Path(path).read_text(encoding="utf-8", errors="replace")


def detect_hardware() -> dict:
    device = "cuda" if torch.cuda.is_available() else "cpu"
    info = {
        "device": device,
        "cuda_available": torch.cuda.is_available(),
        "cuda_device_count": torch.cuda.device_count(),
    }

    if torch.cuda.is_available():
        info["gpu_name"] = torch.cuda.get_device_name(0)
        info["vram_gb"] = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)

    try:
        if os.name == "nt":
            kernel32 = ctypes.windll.kernel32
            c_ulong = ctypes.c_ulong
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [("dwLength", c_ulong), ("dwMemoryLoad", c_ulong), ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong), ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong), ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            mem = MEMORYSTATUSEX()
            mem.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            kernel32.GlobalMemoryStatusEx(ctypes.byref(mem))
            info["ram_gb"] = mem.ullTotalPhys / (1024 ** 3)
        else:
            info["ram_gb"] = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / (1024 ** 3)
    except Exception:
        info["ram_gb"] = None

    return info


def recommend_batch_size(model, target_memory_gb: float = 2.0) -> int:
    params = count_parameters(model)
    approx_mb = (params * 4) / (1024 ** 2)
    batch_size = max(1, int((target_memory_gb * 1024) / max(approx_mb, 1)))
    return min(batch_size, 64)


def save_checkpoint(model, optimizer, step, config, tokenizer, path: str | os.PathLike[str]) -> str:
    checkpoint = {
        "model_state": model.state_dict(),
        "optimizer_state": optimizer.state_dict(),
        "step": step,
        "config": config,
        "tokenizer_vocab_size": getattr(tokenizer, "vocab_size", 256),
    }
    checkpoint_path = Path(path)
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(checkpoint, checkpoint_path)
    return str(checkpoint_path)


def load_checkpoint(model, optimizer, path: str | os.PathLike[str]) -> dict:
    checkpoint = torch.load(path, map_location="cpu", weights_only=False)
    model.load_state_dict(checkpoint["model_state"])
    if optimizer is not None:
        optimizer.load_state_dict(checkpoint["optimizer_state"])
    return checkpoint


if __name__ == "__main__":
    print("Helpers loaded successfully.")
