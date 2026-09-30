import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import uvicorn

HOST = os.getenv("FILE_SERVER_HOST", "0.0.0.0")
PORT = int(os.getenv("FILE_SERVER_PORT", 18804))

app = FastAPI()

app.mount(
    "/webfile",
    StaticFiles(directory="/mnt/ddata2/cc007/MinerU-2.6.6/my_project"),
    name="webfile",
)

if __name__ == "__main__":
    uvicorn.run(
        "file_http_service:app",
        host=HOST,
        port=PORT,
    )
