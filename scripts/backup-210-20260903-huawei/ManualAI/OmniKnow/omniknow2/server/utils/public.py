import base64
import hashlib
import html
import re
import unicodedata

from uuid_extensions import uuid7

from core.acl.schema import ResourceType
from schemas.task import ALLOWED_EXTENSIONS


def replace_slashes_with_arrows(path: str) -> str:
    """
    将路径字符串中的斜杠替换为箭头符号。

    参数:
    path (str): 输入的路径字符串。

    返回:
    str: 替换后的字符串。
    """
    # 去除首尾的斜杠
    trimmed_str = path.strip('/')
    # 替换剩余的斜杠为 "->"
    result_str = trimmed_str.replace('/', '->')
    return result_str


def str_to_base64(string: str) -> str:
    """
    将字符串转换为base64形式
    :param string:
    :return:
    """
    try:
        base64_str = base64.b64encode(string.encode()).decode()
        return base64_str
    except Exception:
        raise ValueError("请求入参无效")


def base64_to_str(base64_str: str) -> str:
    """
    将base64字符串转换为字符串
    :param base64_str:
    :return:
    """
    try:
        string = base64.b64decode(base64_str).decode()
        return string
    except Exception:
        raise ValueError("请求入参无效")

def hash_md5(string: str) -> str:
    """
    计算字符串的MD5值
    :param string:
    :return:
    """
    return hashlib.md5(string.encode()).hexdigest()


def hash_sha512(string: str) -> str:
    """
    计算字符串的SHA512值
    :param string:
    :return:
    """
    return hashlib.sha512(string.encode()).hexdigest()


def allowed_file(filename: str) -> bool:
    if "." in filename:
        ext = filename.rsplit(".", 1)[-1].lower()
        return ext in ALLOWED_EXTENSIONS
    return False


async def check_file_source(file_name: str) -> str:
    file_types = {
        "document": ["docx", "doc", "pdf", "txt", "md", "markdown", "pptx", "ppt", "xlsx", "xls"],
        "image": ["jpg", "jpeg", "png", "gif", "bmp", "tiff", "svg"],
        "video": ["mp4", "avi", "mov", "wmv", "flv", "mkv"],
        "audio": ["mp3", "wav", "aac", "flac", "ogg"],
        "drawing": ["cad", "dwg", "dxf"],
        "html": ["html", "htm", "xhtml"],
    }

    try:
        file_type = file_name.rsplit(".", 1)[-1].lower()
    except IndexError:
        return "unknown"

    for category, extensions in file_types.items():
        if file_type in extensions:
            return category

    return "unknown"


async def get_file_extension(file_name: str) -> str:
    """
    获取文件扩展名
    :param file_name:
    :return:
    """
    try:
        file_extension = file_name.rsplit(".", 1)[-1].lower()
        return file_extension
    except IndexError:
        return ""


def generate_uuid7() -> str:
    """
    生成 UUIDv7
    :return:
    """
    return str(uuid7())


def clean_ocr_text(text: str) -> str:
    """清洗 OCR 文本，统一字符表示"""
    # 1. Unicode 归一化（NFC：组合字符归一；NFKC：同时处理全角/半角）
    text = unicodedata.normalize("NFKC", text)
    # 2. 去除零宽和不可见字符
    invisible = re.compile(
        r'[\u200b-\u200f\u202a-\u202e\u2060-\u2064\ufeff\u00ad]'
    )
    text = invisible.sub('', text)
    # 3. 去除 Unicode 控制字符（保留换行/制表符）
    text = ''.join(
        ch for ch in text
        if unicodedata.category(ch) not in ('Cc', 'Cf')  # Control / Format
        or ch in ('\n', '\r', '\t')
    )
    # 4. 统一换行符
    text = text.replace('\r\n', '\n').replace('\r', '\n').replace('\n', '').replace('\t', '').replace(' ', '')
    return text


def count_chars(text: str, count_spaces: bool = True) -> int:
    """统计'视觉字符数'（归一化后）"""
    cleaned = clean_ocr_text(text)
    if not count_spaces:
        cleaned = cleaned.replace(' ', '')
    return len(cleaned)


async def get_pdf_cover(pdf_path: str, dpi: int = 150):
    import fitz
    doc = fitz.open(pdf_path)
    page = doc[0]  # 首页

    mat = fitz.Matrix(dpi / 72, dpi / 72)  # 72 是 PDF 默认 DPI
    pix = page.get_pixmap(matrix=mat)
    # pix.save(output_path)
    image_bytes = pix.tobytes("png")
    doc.close()
    return image_bytes


async def get_resource_type(ext: str) -> ResourceType:
    if ext in ["docx", "doc", "pdf", "txt", "md", "markdown", "pptx", "ppt", "xlsx", "xls"]:
        return ResourceType.doc
    elif ext in ["jpg", "jpeg", "png", "gif", "bmp", "tiff", "svg"]:
        return ResourceType.image
    elif ext in ["mp4", "avi", "mov", "wmv", "flv", "mkv"]:
        return ResourceType.video
    elif ext in ["mp3", "wav", "aac", "flac", "ogg"]:
        return ResourceType.audio
    elif ext in ["html", "htm", "xhtml"]:
        return ResourceType.rich_text
    else:
        raise NotImplementedError