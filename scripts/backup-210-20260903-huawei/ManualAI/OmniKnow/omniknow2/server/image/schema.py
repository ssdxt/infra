from enum import Enum


ALLOWED_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/bmp",
    "image/webp",
}

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "bmp", "webp"}


class ImgFatherType(str, Enum):
    kbase = "kbase"
    course = "course"
    question = "question"
    paper = "paper"
