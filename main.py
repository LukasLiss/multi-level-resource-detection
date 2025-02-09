from typing import Annotated

import aiofiles
import os

from totmminer import minetotm

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI()

origins = [
    "*"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.get("/totm")
async def get_totm(fileid: str):
    if not fileid:
        raise HTTPException(status_code=400, detail="FileID missing")
    totm = minetotm(fileid)
    return totm


@app.post("/uploadfile/")
async def uploadfile(file: UploadFile):
    # store file and generate unique id
    id = file.filename
    number_to_add = 1
    while os.path.isfile("./uploaded-files/" + id):
        id = str(number_to_add) + file.filename
        number_to_add += 1

    async with aiofiles.open("./uploaded-files/" + id, 'wb') as out_file:
        while content := await file.read(1024):  # async read chunk
            await out_file.write(content)  # async write chunk

    return {"filename": file.filename, "file-id":id}
