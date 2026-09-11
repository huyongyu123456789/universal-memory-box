from pathlib import Path
import shutil
from memorybox.model_manager import managed_model_path

src = managed_model_path()
dst = Path("MemoryBox-Neural-Model-Pack-v0.16.0")
if not src.is_dir():
    raise SystemExit(f"model cache missing: {src}")
shutil.copytree(src, dst, dirs_exist_ok=True)
shutil.copy2("docs/NEURAL_MODEL.md", dst / "README-MemoryBox.md")
print(dst)
