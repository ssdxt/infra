import torch
print("torch", torch.__version__, "cuda", torch.cuda.is_available(), "dev", torch.cuda.device_count())
import transformers
print("transformers", transformers.__version__)
import cv2
print("cv2", cv2.__version__)
import onnxruntime as ort
print("onnxruntime", ort.__version__, ort.get_available_providers())
import pypdfium2
print("pypdfium2 ok")
import mineru
print("mineru import ok")
