import os
from mineru.utils.config_reader import get_config, CONFIG_FILE_NAME
print("CONFIG_FILE_NAME =", CONFIG_FILE_NAME)
import inspect
src = inspect.getsource(__import__("mineru.utils.config_reader", fromlist=["x"]).get_config)
print(src[:800])
cfg = get_config()
print("config keys =", list(cfg.keys()) if isinstance(cfg, dict) else type(cfg))
print("models-dir =", cfg.get("models-dir") if isinstance(cfg, dict) else None)
print("env MINERU_MODEL_SOURCE =", os.getenv("MINERU_MODEL_SOURCE"))
