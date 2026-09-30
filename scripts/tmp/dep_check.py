import importlib
mods = ["torch", "torchvision", "transformers", "onnx", "onnxruntime", "pypdfium2", "cv2", "vllm", "numpy", "PIL"]
for m in mods:
    try:
        mod = importlib.import_module(m)
        print(m, "OK", getattr(mod, "__version__", ""))
    except Exception as e:
        print(m, "MISSING", str(e)[:60])
import sys
print("python", sys.version.split()[0])
