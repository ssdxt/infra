#!/bin/bash
echo "== my-pytorch-embed 内依赖 =="
docker run --rm --entrypoint python3 my-pytorch-embed:latest -c "
import torch
print('torch', torch.__version__, 'cuda', torch.cuda.is_available())
try:
    import transformers; print('transformers', transformers.__version__)
except Exception as e: print('no transformers', e)
for m in ['PIL','dotenv','loguru','fastapi','uvicorn','pydantic']:
    try:
        mod=__import__(m); print(m,'ok',getattr(mod,'__version__',''))
    except Exception as e: print(m,'MISSING',e)
"
