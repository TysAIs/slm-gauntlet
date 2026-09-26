
import shutil, subprocess, platform, re

def detect_device():
    """Return (name, vram_total_mb, kind). kind in {nvidia, amd, apple, cpu}."""
    # NVIDIA
    if shutil.which("nvidia-smi"):
        try:
            r = subprocess.run(["nvidia-smi","--query-gpu=name,memory.total","--format=csv,noheader,nounits"],
                               capture_output=True, text=True, timeout=10)
            name, mb = r.stdout.strip().splitlines()[0].split(", ")
            return name.strip(), int(float(mb)), "nvidia"
        except Exception: pass
    # Apple Silicon (unified memory = total RAM usable as VRAM)
    if platform.system() == "Darwin" and platform.machine() == "arm64":
        try:
            r = subprocess.run(["sysctl","-n","machdep.cpu.brand_string"], capture_output=True, text=True, timeout=5)
            chip = r.stdout.strip()
            r = subprocess.run(["sysctl","-n","hw.memsize"], capture_output=True, text=True, timeout=5)
            total_mb = int(r.stdout.strip()) // (1024*1024)
            return f"Apple {chip.split('Apple ')[-1]}", total_mb, "apple"
        except Exception: pass
    # AMD ROCm
    if shutil.which("rocm-smi"):
        try:
            r = subprocess.run(["rocm-smi","--showproductname","--showmeminfo","vram","--csv"],
                               capture_output=True, text=True, timeout=10)
            # parse best-effort
            for ln in r.stdout.splitlines():
                if "Card series" in ln or "vram" in ln.lower():
                    pass
            return "AMD GPU", 0, "amd"
        except Exception: pass
    return "CPU", 0, "cpu"

if __name__ == "__main__":
    print(detect_device())
