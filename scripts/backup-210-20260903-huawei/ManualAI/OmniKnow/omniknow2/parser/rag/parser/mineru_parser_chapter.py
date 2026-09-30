from __future__ import annotations
import shutil
import requests
import asyncio
import os
import zipfile
import json
import argparse
import base64
import subprocess
import tempfile
import re
import logging
import uuid
from uuid import uuid4
from datetime import datetime
from pathlib import Path
import httpx
from typing import Any, Dict, List, Optional, Tuple, Union
from pydantic import BaseModel, Field
from openai import AsyncOpenAI
from dotenv import load_dotenv
from schema import ChunkModel
from openai import OpenAI

load_dotenv()

async_client = AsyncOpenAI(base_url=os.getenv("BASE_URL"), api_key=os.getenv("API_KEY"))
sem = asyncio.Semaphore(int(os.getenv("SEM_CONCURRENT")))

title_cor_prompt = """
我有一个文档标题列表，请帮我判断每个标题的级别。  

标题级别定义如下：
- 一级标题: text_level=1
- 二级标题: text_level=2
- 三级标题: text_level=3
- 四级标题: text_level=4
- 五级标题: text_level=5
- 六级标题: text_level=6

请返回 JSON 格式，列表中每个元素包含：
{{
"title": "<标题文本>",
"text_level": <级别数字>
}}

标题列表如下：
{}

请只输出 JSON，不要添加其他说明。
"""

summary_prompt = """
你是一名专业的文档分析助手。

任务：
根据给定的文档目录结构，推断该文档的主题和主要内容，并生成一段结构化总结。

要求：
1. 输入仅包含文档目录标题。
2. 根据目录层级关系理解文档结构。
3. 总结需要包括：
   - 文档主题
   - 文档摘要
4. 不要逐条解释目录，而是进行整体概括。
5. 如果部分标题信息不足，可以合理推断。

输出 JSON 格式：

{{
  "document_topic": "文档主题",
  "document_summary": "完整总结（200~400字）"
}}

输入目录：
{}
"""

class MineruExecutionError(Exception):
    """catch mineru error"""

    def __init__(self, return_code, error_msg):
        self.return_code = return_code
        self.error_msg = error_msg
        super().__init__(
            f"Mineru command failed with return code {return_code}: {error_msg}"
        )


class Parser:
    """
    Base class for document parsing utilities.

    Defines common functionality and constants for parsing different document types.
    """

    # Define common file formats
    OFFICE_FORMATS = {".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx"}
    IMAGE_FORMATS = {".png", ".jpeg", ".jpg", ".bmp", ".tiff", ".tif", ".gif", ".webp"}
    TEXT_FORMATS = {".txt", ".md"}

    # Class-level logger
    logger = logging.getLogger(__name__)

    def __init__(self) -> None:
        """Initialize the base parser."""
        pass

    @staticmethod
    def convert_office_to_pdf(
        doc_path: Union[str, Path], output_dir: Optional[str] = None
    ) -> Path:
        """
        Convert Office document (.doc, .docx, .ppt, .pptx, .xls, .xlsx) to PDF.
        Requires LibreOffice to be installed.

        Args:
            doc_path: Path to the Office document file
            output_dir: Output directory for the PDF file

        Returns:
            Path to the generated PDF file
        """
        try:
            # Convert to Path object for easier handling
            doc_path = Path(doc_path)
            if not doc_path.exists():
                raise FileNotFoundError(f"Office document does not exist: {doc_path}")

            name_without_suff = doc_path.stem

            # Prepare output directory
            if output_dir:
                base_output_dir = Path(output_dir)
            else:
                # base_output_dir = doc_path.parent / "libreoffice_output"
                current_dir = os.path.dirname(os.path.abspath(__file__))
                base_output_dir = Path(os.path.join(current_dir, "./libreoffice_output"))

            base_output_dir.mkdir(parents=True, exist_ok=True)

            # Create temporary directory for PDF conversion
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                # Convert to PDF using LibreOffice
                logging.info(f"Converting {doc_path.name} to PDF using LibreOffice...")

                # Prepare subprocess parameters to hide console window on Windows
                import platform

                # Try LibreOffice commands in order of preference
                commands_to_try = ["libreoffice", "soffice"]

                conversion_successful = False
                for cmd in commands_to_try:
                    try:
                        convert_cmd = [
                            cmd,
                            "--headless",
                            "--convert-to",
                            "pdf",
                            "--outdir",
                            str(temp_path),
                            str(doc_path),
                        ]

                        # Prepare conversion subprocess parameters
                        convert_subprocess_kwargs = {
                            "capture_output": True,
                            "text": True,
                            "timeout": 60,  # 60 second timeout
                            "encoding": "utf-8",
                            "errors": "ignore",
                        }

                        # Hide console window on Windows
                        if platform.system() == "Windows":
                            convert_subprocess_kwargs["creationflags"] = (
                                subprocess.CREATE_NO_WINDOW
                            )

                        result = subprocess.run(
                            convert_cmd, **convert_subprocess_kwargs
                        )

                        if result.returncode == 0:
                            conversion_successful = True
                            logging.info(
                                f"Successfully converted {doc_path.name} to PDF using {cmd}"
                            )
                            break
                        else:
                            logging.warning(
                                f"LibreOffice command '{cmd}' failed: {result.stderr}"
                            )
                    except FileNotFoundError:
                        logging.warning(f"LibreOffice command '{cmd}' not found")
                    except subprocess.TimeoutExpired:
                        logging.warning(f"LibreOffice command '{cmd}' timed out")
                    except Exception as e:
                        logging.error(
                            f"LibreOffice command '{cmd}' failed with exception: {e}"
                        )

                if not conversion_successful:
                    raise RuntimeError(
                        f"LibreOffice conversion failed for {doc_path.name}. "
                        f"Please ensure LibreOffice is installed:\n"
                        "- Windows: Download from https://www.libreoffice.org/download/download/\n"
                        "- macOS: brew install --cask libreoffice\n"
                        "- Ubuntu/Debian: sudo apt-get install libreoffice\n"
                        "- CentOS/RHEL: sudo yum install libreoffice\n"
                        "Alternatively, convert the document to PDF manually."
                    )

                # Find the generated PDF
                pdf_files = list(temp_path.glob("*.pdf"))
                if not pdf_files:
                    raise RuntimeError(
                        f"PDF conversion failed for {doc_path.name} - no PDF file generated. "
                        f"Please check LibreOffice installation or try manual conversion."
                    )

                pdf_path = pdf_files[0]
                logging.info(
                    f"Generated PDF: {pdf_path.name} ({pdf_path.stat().st_size} bytes)"
                )

                # Validate the generated PDF
                if pdf_path.stat().st_size < 100:  # Very small file, likely empty
                    raise RuntimeError(
                        "Generated PDF appears to be empty or corrupted. "
                        "Original file may have issues or LibreOffice conversion failed."
                    )

                # Copy PDF to final output directory
                final_pdf_path = base_output_dir / f"{name_without_suff}.pdf"
                shutil.copy2(pdf_path, final_pdf_path)

                return final_pdf_path

        except Exception as e:
            logging.error(f"Error in convert_office_to_pdf: {str(e)}")
            raise

    @staticmethod
    def convert_text_to_pdf(
        text_path: Union[str, Path], output_dir: Optional[str] = None
    ) -> Path:
        """
        Convert text file (.txt, .md) to PDF using ReportLab with full markdown support.

        Args:
            text_path: Path to the text file
            output_dir: Output directory for the PDF file

        Returns:
            Path to the generated PDF file
        """
        try:
            text_path = Path(text_path)
            if not text_path.exists():
                raise FileNotFoundError(f"Text file does not exist: {text_path}")

            # Supported text formats
            supported_text_formats = {".txt", ".md"}
            if text_path.suffix.lower() not in supported_text_formats:
                raise ValueError(f"Unsupported text format: {text_path.suffix}")

            # Read the text content
            try:
                with open(text_path, "r", encoding="utf-8") as f:
                    text_content = f.read()
            except UnicodeDecodeError:
                # Try with different encodings
                for encoding in ["gbk", "latin-1", "cp1252"]:
                    try:
                        with open(text_path, "r", encoding=encoding) as f:
                            text_content = f.read()
                        logging.info(f"Successfully read file with {encoding} encoding")
                        break
                    except UnicodeDecodeError:
                        continue
                else:
                    raise RuntimeError(
                        f"Could not decode text file {text_path.name} with any supported encoding"
                    )

            # Prepare output directory
            if output_dir:
                base_output_dir = Path(output_dir)
            else:
                # base_output_dir = text_path.parent / "reportlab_output"
                current_dir = os.path.dirname(os.path.abspath(__file__))
                base_output_dir = Path(os.path.join(current_dir, "./reportlab_output"))


            base_output_dir.mkdir(parents=True, exist_ok=True)
            pdf_path = base_output_dir / f"{text_path.stem}.pdf"

            # Convert text to PDF
            logging.info(f"Converting {text_path.name} to PDF...")

            try:
                from reportlab.lib.pagesizes import A4
                from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
                from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
                from reportlab.lib.units import inch
                from reportlab.pdfbase import pdfmetrics
                from reportlab.pdfbase.ttfonts import TTFont
                from reportlab.pdfbase.cidfonts import UnicodeCIDFont

                support_chinese = True

                # Create PDF document
                doc = SimpleDocTemplate(
                    str(pdf_path),
                    pagesize=A4,
                    leftMargin=inch,
                    rightMargin=inch,
                    topMargin=inch,
                    bottomMargin=inch,
                )

                # Get styles
                styles = getSampleStyleSheet()
                normal_style = styles["Normal"]
                heading_style = styles["Heading1"]
                
                pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
                if support_chinese:
                    normal_style.fontName = "STSong-Light"
                    heading_style.fontName = "STSong-Light"

                # Try to register a font that supports Chinese characters
                try:
                    # Try to use system fonts that support Chinese
                    import platform

                    system = platform.system()
                    if system == "Windows":
                        # Try common Windows fonts
                        for font_name in ["SimSun", "SimHei", "Microsoft YaHei"]:
                            try:
                                from reportlab.pdfbase.cidfonts import (
                                    UnicodeCIDFont,
                                )

                                pdfmetrics.registerFont(UnicodeCIDFont(font_name))
                                normal_style.fontName = font_name
                                heading_style.fontName = font_name
                                break
                            except Exception:
                                continue
                    elif system == "Darwin":  # macOS
                        for font_name in ["STSong-Light", "STHeiti"]:
                            try:
                                from reportlab.pdfbase.cidfonts import (
                                    UnicodeCIDFont,
                                )

                                pdfmetrics.registerFont(UnicodeCIDFont(font_name))
                                normal_style.fontName = font_name
                                heading_style.fontName = font_name
                                break
                            except Exception:
                                continue
                except Exception:
                    pass  # Use default fonts if Chinese font setup fails

                # Build content
                story = []

                # Handle markdown or plain text
                if text_path.suffix.lower() == ".md":
                    # Handle markdown content - simplified implementation
                    lines = text_content.split("\n")
                    for line in lines:
                        line = line.strip()
                        if not line:
                            story.append(Spacer(1, 12))
                            continue

                        # Headers
                        if line.startswith("#"):
                            level = len(line) - len(line.lstrip("#"))
                            header_text = line.lstrip("#").strip()
                            if header_text:
                                header_style = ParagraphStyle(
                                    name=f"Heading{level}",
                                    parent=heading_style,
                                    fontSize=max(16 - level, 10),
                                    spaceAfter=8,
                                    spaceBefore=16 if level <= 2 else 12,
                                )
                                story.append(Paragraph(header_text, header_style))
                        else:
                            # Regular text
                            story.append(Paragraph(line, normal_style))
                            story.append(Spacer(1, 6))
                else:
                    # Handle plain text files (.txt)
                    logging.info(
                        f"Processing plain text file with {len(text_content)} characters..."
                    )

                    # Split text into lines and process each line
                    lines = text_content.split("\n")
                    line_count = 0

                    for line in lines:
                        line = line.rstrip()
                        line_count += 1

                        # Empty lines
                        if not line.strip():
                            story.append(Spacer(1, 6))
                            continue

                        # Regular text lines
                        # Escape special characters for ReportLab
                        safe_line = (
                            line.replace("&", "&amp;")
                            .replace("<", "&lt;")
                            .replace(">", "&gt;")
                        )

                        # Create paragraph
                        story.append(Paragraph(safe_line, normal_style))
                        story.append(Spacer(1, 3))

                    logging.info(f"Added {line_count} lines to PDF")

                    # If no content was added, add a placeholder
                    if not story:
                        story.append(Paragraph("(Empty text file)", normal_style))

                # Build PDF
                doc.build(story)
                logging.info(
                    f"Successfully converted {text_path.name} to PDF ({pdf_path.stat().st_size / 1024:.1f} KB)"
                )

            except ImportError:
                raise RuntimeError(
                    "reportlab is required for text-to-PDF conversion. "
                    "Please install it using: pip install reportlab"
                )
            except Exception as e:
                raise RuntimeError(
                    f"Failed to convert text file {text_path.name} to PDF: {str(e)}"
                )

            # Validate the generated PDF
            if not pdf_path.exists() or pdf_path.stat().st_size < 100:
                raise RuntimeError(
                    f"PDF conversion failed for {text_path.name} - generated PDF is empty or corrupted."
                )

            return pdf_path

        except Exception as e:
            logging.error(f"Error in convert_text_to_pdf: {str(e)}")
            raise
        
    @staticmethod
    def _process_inline_markdown(text: str) -> str:
        """
        Process inline markdown formatting (bold, italic, code, links)

        Args:
            text: Raw text with markdown formatting

        Returns:
            Text with ReportLab markup
        """
        # Escape special characters for ReportLab
        text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        # Bold text: **text** or __text__
        text = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", text)
        text = re.sub(r"__(.*?)__", r"<b>\1</b>", text)

        # Italic text: *text* or _text_ (but not in the middle of words)
        text = re.sub(r"(?<!\w)\*([^*\n]+?)\*(?!\w)", r"<i>\1</i>", text)
        text = re.sub(r"(?<!\w)_([^_\n]+?)_(?!\w)", r"<i>\1</i>", text)

        # Inline code: `code`
        text = re.sub(
            r"`([^`]+?)`",
            r'<font name="Courier" size="9" color="darkred">\1</font>',
            text,
        )

        # Links: [text](url) - convert to text with URL annotation
        def link_replacer(match):
            link_text = match.group(1)
            url = match.group(2)
            return f'<link href="{url}" color="blue"><u>{link_text}</u></link>'

        text = re.sub(r"\[([^\]]+?)\]\(([^)]+?)\)", link_replacer, text)

        # Strikethrough: ~~text~~
        text = re.sub(r"~~(.*?)~~", r"<strike>\1</strike>", text)

        return text

    def parse_pdf(
        self,
        pdf_path: Union[str, Path],
        output_dir: Optional[str] = None,
        method: str = "auto",
        lang: Optional[str] = None,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """
        Abstract method to parse PDF document.
        Must be implemented by subclasses.

        Args:
            pdf_path: Path to the PDF file
            output_dir: Output directory path
            method: Parsing method (auto, txt, ocr)
            lang: Document language for OCR optimization
            **kwargs: Additional parameters for parser-specific command

        Returns:
            List[Dict[str, Any]]: List of content blocks
        """
        raise NotImplementedError("parse_pdf must be implemented by subclasses")

    def parse_image(
        self,
        image_path: Union[str, Path],
        output_dir: Optional[str] = None,
        lang: Optional[str] = None,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """
        Abstract method to parse image document.
        Must be implemented by subclasses.

        Note: Different parsers may support different image formats.
        Check the specific parser's documentation for supported formats.

        Args:
            image_path: Path to the image file
            output_dir: Output directory path
            lang: Document language for OCR optimization
            **kwargs: Additional parameters for parser-specific command

        Returns:
            List[Dict[str, Any]]: List of content blocks
        """
        raise NotImplementedError("parse_image must be implemented by subclasses")

def filter_json(json_str):
    if str(json_str).startswith("```json"):
        json_str= json_str[len("```json"):]
    if str(json_str).startswith("```"):
        json_str= json_str[len("```"):]
    if str(json_str).endswith("```json"):
        json_str= json_str[:-7]
    if str(json_str).endswith("```"):
        json_str= json_str[:-3]
    return json_str


def sanitize_filename(filename: str) -> str:
    """
    格式化压缩文件的文件名
    移除路径遍历字符, 保留 Unicode 字母、数字、._-
    禁止隐藏文件
    """
    sanitized = re.sub(r'[/\\\.]{2,}|[/\\]', '', filename)
    sanitized = re.sub(r'[^\w.-]', '_', sanitized, flags=re.UNICODE)
    if sanitized.startswith('.'):
        sanitized = '_' + sanitized[1:]
    return sanitized or 'unnamed'


def _normalize_bbox(bbox: Any) -> List[Any]:
    """规范化 bbox 为列表格式"""
    if bbox is None:
        return []
    if isinstance(bbox, list):
        if len(bbox) == 4 and all(isinstance(x, (int, float)) for x in bbox):
            return [bbox]
        return bbox
    return []


def _normalize_page_idx(page_idx: Any) -> List[Any]:
    """规范化 page_idx 为列表格式"""
    if page_idx is None:
        return []
    if isinstance(page_idx, (int, float)):
        return [page_idx]
    if isinstance(page_idx, list):
        return page_idx
    return []


def _split_chunk_by_size(
    content: str,
    bbox_list: List[Any],
    page_idx_list: List[Any],
    size: Optional[int],
) -> List[Tuple[str, List[Any], List[Any]]]:
    """按 chunk_size 硬切分内容，bbox 和 page_idx 按比例划分"""
    if size is None or size <= 0 or len(content) <= size:
        return [(content, bbox_list, page_idx_list)]

    chunks: List[Tuple[str, List[Any], List[Any]]] = []
    num_chunks = (len(content) + size - 1) // size
    bbox_per_chunk = len(bbox_list) / num_chunks if bbox_list else 0
    page_idx_per_chunk = len(page_idx_list) / num_chunks if page_idx_list else 0

    for i in range(num_chunks):
        start_idx = i * size
        end_idx = min((i + 1) * size, len(content))
        chunk_content = content[start_idx:end_idx]
        bbox_start = int(i * bbox_per_chunk)
        bbox_end = int((i + 1) * bbox_per_chunk) if i < num_chunks - 1 else len(bbox_list)
        chunk_bbox = bbox_list[bbox_start:bbox_end] if bbox_list else []
        page_idx_start = int(i * page_idx_per_chunk)
        page_idx_end = int((i + 1) * page_idx_per_chunk) if i < num_chunks - 1 else len(page_idx_list)
        chunk_page_idx = page_idx_list[page_idx_start:page_idx_end] if page_idx_list else []
        chunks.append((chunk_content, chunk_bbox, chunk_page_idx))
    return chunks


def _extract_zip_no_root(zip_path, extract_to, root_dir):
    logging.info(f"[MinerU] Extract zip: zip_path={zip_path}, extract_to={extract_to}, root_hint={root_dir}")
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        if not root_dir:
            files = zip_ref.namelist()
            if files and files[0].endswith("/"):
                root_dir = files[0]
            else:
                root_dir = None

        if not root_dir or not root_dir.endswith("/"):
            logging.info(f"[MinerU] No root directory found, extracting all (root_hint={root_dir})")
            zip_ref.extractall(extract_to)
            return

        root_len = len(root_dir)
        for member in zip_ref.infolist():
            filename = member.filename
            if filename == root_dir:
                logging.debug("[MinerU] Ignore root folder")
                continue

            path = filename
            if path.startswith(root_dir):
                path = path[root_len:]

            full_path = os.path.join(extract_to, path)
            if member.is_dir():
                os.makedirs(full_path, exist_ok=True)
            else:
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, "wb") as f:
                    f.write(zip_ref.read(filename))

class MineruParser(Parser):
    """
    MinerU 2.0 document parsing utility class

    Supports parsing PDF and image documents, converting the content into structured data
    and generating markdown and JSON output.

    Note: Office documents are no longer directly supported. Please convert them to PDF first.
    """

    __slots__ = ()

    # Class-level logger
    logger = logging.getLogger(__name__)
    mineru_api=os.getenv("MINERU_API")

    def __init__(self) -> None:
        """Initialize MineruParser"""
        super().__init__()
      
                 
                        
    @staticmethod
    async def _run_mineru_api(input_path: Path, output_dir: Path, method: str = "auto", backend: str = "pipeline", lang: Optional[str] = None, mineru_api="http://127.0.0.1:8000", **kwargs):
        start_page_id = kwargs.get("start_page_id",0)
        end_page_id = kwargs.get("end_page_id",99999)

        output_zip_path = os.path.join(str(output_dir), "output.zip")

        pdf_file_path = str(input_path)

        if not os.path.exists(pdf_file_path):
            raise RuntimeError(f"[MinerU] PDF file not exists: {pdf_file_path}")

        pdf_file_name = Path(pdf_file_path).stem.strip()
        safe_pdf_name = sanitize_filename(pdf_file_name)
        
        output_path = os.path.join(str(output_dir), pdf_file_name, method)
        os.makedirs(output_path, exist_ok=True)

        data = {
            "output_dir": "./output",
            "lang_list": lang,
            "backend": backend,
            "parse_method": method,
            # "formula_enable": True,
            "formula_enable": kwargs.get("formula", False),
            "table_enable": True,
            "server_url": os.getenv("VL_SERVER_URL"),
            "return_md": True,
            "return_middle_json": True,
            "return_model_output": True,
            "return_content_list": True,
            "return_images": True,
            "response_format_zip": True,
            "start_page_id": start_page_id,
            "end_page_id": end_page_id,
        }

        headers = {"Accept": "application/json"}
        try:
            logging.info(f"[MinerU] invoke api: {mineru_api}/file_parse")

            # response = requests.post(url=f"{mineru_api}/file_parse", files=files, data=data, headers=headers, timeout=1800)
            timeout = httpx.Timeout(1800.0)
            # response.raise_for_status()
            async with httpx.AsyncClient(timeout=timeout) as client:
                with open(pdf_file_path, "rb") as f:
                    files = {
                        "files": (pdf_file_name + ".pdf", f, "application/pdf")
                    }

                    response = await client.post(
                        url=f"{mineru_api}/file_parse",
                        files=files,
                        data=data,
                        headers=headers,
                    )

                response.raise_for_status()
                content_type = response.headers.get("Content-Type", "")
                if "application/zip" in content_type:
            
                    logging.info(f"[MinerU] zip file returned, saving to {output_zip_path}...")


                    with open(output_zip_path, "wb") as f:
                        f.write(response.content)

                    logging.info(f"[MinerU] Unzip to {output_path}...")
                    # _extract_zip_no_root(output_zip_path, output_path, pdf_file_name + "/")
                    _extract_zip_no_root(output_zip_path, output_path, safe_pdf_name + "/")
                    

                else:
                    logging.warning("[MinerU] not zip returned from api：%s " % response.headers.get("Content-Type"))
        except Exception as e:
            raise RuntimeError(f"[MinerU] api failed with exception {e}")
        logging.info("[MinerU] Api completed successfully.")


    @staticmethod
    def update_title_level(file_path: str):
        # 读取 JSON 文件
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 递归提取标题
        def extract_text_with_level(obj):
            results = []
            if isinstance(obj, dict):
                if "text_level" in obj and "text" in obj:
                    results.append(obj["text"])
                for value in obj.values():
                    results.extend(extract_text_with_level(value))
            elif isinstance(obj, list):
                for item in obj:
                    results.extend(extract_text_with_level(item))
            return results

        titles = extract_text_with_level(data)

        # 构造 Prompt


        base_url = os.getenv("TITLE_CORRECTION_BASE_URL", os.getenv("BASE_URL", ""))
        api_key = os.getenv("TITLE_CORRECTION_API_KEY", os.getenv("API_KEY", ""))
        if not base_url or not api_key:
            raise RuntimeError(
                "Title correction requires TITLE_CORRECTION_BASE_URL and TITLE_CORRECTION_API_KEY "
                "(or BASE_URL and API_KEY) in environment"
            )
        client = OpenAI(base_url=base_url, api_key=api_key)

        response = client.chat.completions.create(
            model=os.getenv("TITLE_MODEL_NAME", os.getenv("MODEL_NAME", "")),
            messages=[{"role": "user", "content": title_cor_prompt.format(titles)}],
            stream=False,
        )

        text_output = response.choices[0].message.content

        # 解析 JSON
        try:
            text_output = filter_json(text_output)
            result = json.loads(text_output)
        except json.JSONDecodeError:
            logging.error("解析 JSON 失败，模型输出如下：%s", text_output)
            return

        # 构建映射
        title_to_level = {item["title"]: item["text_level"] for item in result}

        # 更新 JSON
        def update_text_level(obj):
            if isinstance(obj, dict):
                if "text_level" in obj and "text" in obj:
                    if obj["text"] in title_to_level:
                        old_level = obj["text_level"]
                        new_level = title_to_level[obj["text"]]
                        if old_level != new_level:
                            logging.debug(
                                "标题: %s, 原 level: %s -> 新 level: %s",
                                obj["text"], old_level, new_level,
                            )
                        obj["text_level"] = new_level
                for value in obj.values():
                    update_text_level(value)
            elif isinstance(obj, list):
                for item in obj:
                    update_text_level(item)

        update_text_level(data)

        # 覆盖写回原文件
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logging.info("已更新 text_level 并覆盖原文件: %s", file_path)

                
        # return filter_json(result2)

    @staticmethod
    def _read_output_files(
        output_dir: Path, file_stem: str, method: str = "auto", title_correction: bool=False
    ) -> Tuple[List[Dict[str, Any]], str]:
        """
        Read the output files generated by mineru

        Args:
            output_dir: Output directory
            file_stem: File name without extension

        Returns:
            Tuple containing (content list JSON, Markdown text)
        """
        safe_file_stem = sanitize_filename(file_stem)
        
        # Look for the generated files
        md_file = output_dir / f"{file_stem}.md"
        json_file = output_dir / f"{file_stem}_content_list.json"
        images_base_dir = output_dir  # Base directory for images

        file_stem_subdir = output_dir / file_stem
        if file_stem_subdir.exists():
            # md_file = file_stem_subdir / method / f"{file_stem}.md"
            # json_file = file_stem_subdir / method / f"{file_stem}_content_list.json"
            # images_base_dir = file_stem_subdir / method
            method_dir = file_stem_subdir / method
            if method_dir.exists():
                # 在 method 目录下，首先尝试原始文件名
                md_file = method_dir / f"{file_stem}.md"
                json_file = method_dir / f"{file_stem}_content_list.json"
                images_base_dir = method_dir
                
                # 如果原始文件名的文件不存在，尝试安全文件名（因为 ZIP 中可能使用了安全文件名）
                if (not md_file.exists() and not json_file.exists()) and safe_file_stem != file_stem:
                    safe_md_file = method_dir / f"{safe_file_stem}.md"
                    safe_json_file = method_dir / f"{safe_file_stem}_content_list.json"
                    if safe_md_file.exists() or safe_json_file.exists():
                        md_file = safe_md_file
                        json_file = safe_json_file
                        images_base_dir = method_dir
        else:
            # 如果原始文件名目录不存在，尝试使用安全文件名目录
            safe_file_stem_subdir = output_dir / safe_file_stem
            if safe_file_stem_subdir.exists():
                method_dir = safe_file_stem_subdir / method
                if method_dir.exists():
                    md_file = method_dir / f"{safe_file_stem}.md"
                    json_file = method_dir / f"{safe_file_stem}_content_list.json"
                    images_base_dir = method_dir
                    
        # Read markdown content
        md_content = ""
        if md_file.exists():
            try:
                with open(md_file, "r", encoding="utf-8") as f:
                    md_content = f.read()
            except Exception as e:
                logging.warning(f"Could not read markdown file {md_file}: {e}")

        # Read JSON content list
        content_list = []
        if json_file.exists():
            try:
                if title_correction:
                    logging.info(f"标题修正中...")
                    MineruParser.update_title_level(json_file)
                    logging.info(f"标题修正完成")
                
                with open(json_file, "r", encoding="utf-8") as f:
                    content_list = json.load(f)

                # Always fix relative paths in content_list to absolute paths
                logging.info(
                    f"Fixing image paths in {json_file} with base directory: {images_base_dir}"
                )
                for item in content_list:
                    if isinstance(item, dict):
                        for field_name in [
                            "img_path",
                            "table_img_path",
                            "equation_img_path",
                        ]:
                            if field_name in item and item[field_name]:
                                img_path = item[field_name]
                                absolute_img_path = (
                                    images_base_dir / img_path
                                ).resolve()
                                item[field_name] = str(absolute_img_path)
                                logging.debug(
                                    f"Updated {field_name}: {img_path} -> {item[field_name]}"
                                )

            except Exception as e:
                logging.warning(f"Could not read JSON file {json_file}: {e}")

        return content_list, md_content

    def _post_process_chunks(
        self,
        content_list: List[Dict[str, Any]],
        file_id: str,
        file_path: str,
        chunk_source: str,
        chunk_size: Optional[int] = None,
        include_parent_titles=True
    ) -> List[ChunkModel]:
        """
        后处理chunk列表:
        1. 根据标题构建标题层级（同级连续标题合并为一行，不同级标题以\\n拼接）
        2. 每遇到新标题，先结束上一个正文chunk，再基于新标题开启新的chunk范围
        3. 图片和表格单独作为chunk
        4. 合并bbox和page_idx(使用list做append)
        5. 支持chunk_size按字符数硬切分
        6. 转换为ChunkModel格式
        7. 对于表格chunk,others里面放的是html格式的内容(table_body)
        8. 支持可选地在title和content中拼接上级标题

        Args:
            content_list: 原始content列表
            file_id: 文件ID
            file_path: 文件路径
            chunk_source: chunk来源标识
            chunk_size: chunk大小限制(字符数),如果为None则不限制

        Returns:
            List[ChunkModel]: 处理后的ChunkModel列表
        """
        if not content_list:
            return []

        merged_chunks: List[ChunkModel] = []
        current_text_chunk: Optional[Dict[str, Any]] = None
        count = 0
        chunk_index_counter = 0
        

        # 标题层级栈：key 为 text_level，value 为该级标题字符串（已合并同级标题）
        title_stack: Dict[int, str] = {}
        last_title_level: Optional[int] = None
        last_item_is_title: bool = False
        # 当前所属章节（按一级标题划分）
        current_chapter_title: str = ""

        def _generate_chunk_id() -> str:
            """生成chunk_id并递增计数器"""
            nonlocal count
            file_name = os.path.basename(file_path).split(".")[0][:10] if file_path else "chunk"
            chunk_id = f"{file_name}_{uuid4().hex}-{count}"
            count += 1
            return chunk_id

        def _next_chunk_index() -> int:
            """生成按顺序递增的chunk_index"""
            nonlocal chunk_index_counter
            idx = chunk_index_counter
            chunk_index_counter += 1
            return idx

        def _build_title_string() -> str:
            """
            根据当前标题栈构造标题字符串:
            - include_parent_titles=False: 仅返回最下层标题
            - include_parent_titles=True: 返回从上到下用\\n拼接的标题路径
            """
            if not title_stack:
                return ""
            levels = sorted(title_stack.keys())
            if not levels:
                return ""

            if include_parent_titles:
                return "\n".join(title_stack[l] for l in levels if title_stack.get(l))
            # 默认仅使用最近标题
            deepest = max(levels)
            return title_stack.get(deepest, "")

        def _get_current_title() -> str:
            """
            获取当前标题（最深层标题），不受include_parent_titles影响
            始终返回标题栈中最深层的标题
            """
            if not title_stack:
                return ""
            levels = sorted(title_stack.keys())
            if not levels:
                return ""
            deepest = max(levels)
            return title_stack.get(deepest, "")
        
        def _get_parent_title() -> str:
            """
            获取上一级父标题（直接父级标题）
            返回比最深层标题低一级的标题
            """
            if not title_stack:
                return ""
            levels = sorted(title_stack.keys())
            if not levels:
                return ""
            if len(levels) <= 1:
                # 只有一个层级，没有父级标题
                return ""
            deepest = max(levels)
            # 找到比最深层级低一级的层级（直接父级）
            parent_levels = [l for l in levels if l < deepest]
            if not parent_levels:
                return ""
            # 返回最高层级的父级标题（即直接父级）
            parent_level = max(parent_levels)
            return title_stack.get(parent_level, "")
        
        
        def _create_chunk_model(
            content: str,
            title: str,
            cur_title: str,
            bbox_list: List[Any],
            page_idx_list: List[Any],
            bbox_type: str,
            chunk_id: str,
            chunk_index: int,
            chunk_source: str,
            media_path: str = "",
            others: Optional[Dict[str, Any]] = None,
            parent_title: str = "",
            chapter_title: str = "",
            
        ) -> ChunkModel:
            """创建ChunkModel对象"""
            update_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            final_others: Dict[str, Any] = dict(others) if others else {}
            if chapter_title:
                # 为所有 chunk 打上所属章节标记
                final_others.setdefault("chapter_title", chapter_title)
            return ChunkModel(
                chunk_id=chunk_id,
                chunk_index=chunk_index,
                content=content,
                file_id=file_id,
                file_path=file_path,
                update_time=update_time,
                bbox_type=bbox_type,
                title=title,
                cur_title=cur_title,  # 当前chunk的标题
                par_title=parent_title,  # 当前chunk的标题
                summary="",
                media_path=media_path,
                chunk_source=chunk_source,
                bbox=bbox_list,
                page_idx=page_idx_list,
                others=final_others,
            )

        def _flush_current_text_chunk() -> None:
            """将当前文本chunk根据标题和chunk_size刷入merged_chunks"""
            nonlocal current_text_chunk
            if not current_text_chunk:
                return

            content_text = (current_text_chunk.get("content") or "").strip()
            if not content_text:
                current_text_chunk = None
                return

            bbox_list = current_text_chunk.get("bbox", []) or []
            page_idx_list = current_text_chunk.get("page_idx", []) or []

            title_str = _build_title_string()
            parent_title_str = _get_parent_title()
            chapter_title_str = current_chapter_title

            # 内容里是否拼接标题路径
            # if include_parent_titles and title_str:
            #     base_content = f"{title_str}\n{content_text}"
            # else:
            #     base_content = content_text
            base_content = content_text
                
            cur_title_str = _get_current_title()

            for chunk_content, chunk_bbox, chunk_page_idx in _split_chunk_by_size(
                base_content, bbox_list, page_idx_list, chunk_size
            ):
                merged_chunks.append(
                    _create_chunk_model(
                        content=chunk_content,
                        title=title_str,
                        cur_title=cur_title_str,
                        parent_title=parent_title_str,
                        chapter_title=chapter_title_str,
                        bbox_list=chunk_bbox,
                        page_idx_list=chunk_page_idx,
                        bbox_type="text",
                        chunk_id=_generate_chunk_id(),
                        chunk_index=_next_chunk_index(),
                        
                        chunk_source=chunk_source,
                    )
                )

            current_text_chunk = None
       
        for item in content_list:
            if not isinstance(item, dict):
                continue

            content_type = item.get("type", "").lower()

            # 对于type为discarded直接continue
            if content_type == "discarded":
                continue

            text_level = item.get("text_level", 0)
            sub_type = item.get("sub_type", "")
            is_title = text_level is not None and text_level > 0

            # 处理图片和表格: 单独作为chunk
            if content_type == "image":
                # 遇到图片前，先刷掉当前文本chunk
                _flush_current_text_chunk()

                img_caption = item.get("image_caption", [])
                if isinstance(img_caption, list):
                    img_caption = "\n".join(img_caption) if img_caption else ""
                else:
                    img_caption = str(img_caption) if img_caption else ""

                img_path = item.get("img_path", "")
                bbox_list = _normalize_bbox(item.get("bbox"))
                page_idx_list = _normalize_page_idx(item.get("page_idx"))

                title_str = _build_title_string()
                cur_title_str = _get_current_title()
                parent_title_str = _get_parent_title()
                chapter_title_str = current_chapter_title
                

                merged_chunks.append(
                    _create_chunk_model(
                        content=img_caption,
                        title=title_str,
                        cur_title=cur_title_str,
                        parent_title=parent_title_str,
                        chapter_title=chapter_title_str,
                        
                        bbox_list=bbox_list,
                        page_idx_list=page_idx_list,
                        chunk_source=chunk_source,
                        bbox_type="image",
                        chunk_id=_generate_chunk_id(),
                        chunk_index=_next_chunk_index(),
                        media_path=img_path,
                    )
                )
                last_item_is_title = False

            elif content_type == "table":
                # 遇到表格前，先刷掉当前文本chunk
                _flush_current_text_chunk()

                table_body = item.get("table_body", "")
                table_caption = item.get("table_caption", [])
                img_url = item.get("img_path", [])

                if isinstance(table_caption, list):
                    table_caption = "\n".join(table_caption) if table_caption else ""
                else:
                    table_caption = str(table_caption) if table_caption else ""

                table_content = table_caption if table_caption else "表格"
                table_html = table_body if table_body else ""

                bbox_list = _normalize_bbox(item.get("bbox"))
                page_idx_list = _normalize_page_idx(item.get("page_idx"))

                title_str = _build_title_string()
                cur_title_str = _get_current_title()
                parent_title_str = _get_parent_title()
                chapter_title_str = current_chapter_title
                

                merged_chunks.append(
                    _create_chunk_model(
                        content=table_content,
                        title=title_str,
                        cur_title=cur_title_str,
                        parent_title=parent_title_str,
                        chapter_title=chapter_title_str,
                        bbox_list=bbox_list,
                        chunk_source=chunk_source,
                        media_path=img_url,
                        page_idx_list=page_idx_list,
                        bbox_type="table",
                        chunk_id=_generate_chunk_id(),
                        chunk_index=_next_chunk_index(),
                        others={"table_body": table_html} if table_html else {},
                    )
                )
                last_item_is_title = False

            elif content_type == "text" or sub_type=="text":
                if sub_type=="text":
                    list_items = item.get("list_items")
                    text_content = "\n".join(list_items)
                else:
                    text_content = (item.get("text") or "").strip()
                if not text_content:
                    continue

                if is_title:
                    # 新标题到来前，先结束上一段正文
                    _flush_current_text_chunk()

                    # 更新标题栈：同一级别连续标题用空格合并，不同级别则重置下层
                    level = int(text_level)
                    if last_item_is_title and last_title_level == level and level in title_stack:
                        # 同一级别连续标题，空格拼接
                        title_stack[level] = f"{title_stack[level]} {text_content}"
                    else:
                        # 不同级别或首次标题，更新当前级标题，并清理更深层级
                        title_stack[level] = text_content
                        # 清除比当前级别更深的标题
                        keys_to_delete = [l for l in list(title_stack.keys()) if l > level]
                        for k in keys_to_delete:
                            title_stack.pop(k, None)

                    # 一级标题作为“章节标题”
                    if level == 1:
                        current_chapter_title = text_content

                    last_title_level = level
                    last_item_is_title = True

                    # 标题本身不作为单独文本内容进入chunk，只影响后续正文chunk的title
                    current_text_chunk = {
                        "content": "",
                        "bbox": [],
                        "page_idx": [],
                    }
                else:
                    # 普通文本, 合并到当前chunk
                    item_bbox = _normalize_bbox(item.get("bbox"))
                    item_page_idx = _normalize_page_idx(item.get("page_idx"))

                    if current_text_chunk is None:
                        current_text_chunk = {
                            "content": text_content,
                            "bbox": item_bbox,
                            "page_idx": item_page_idx,
                        }
                    else:
                        # 先尝试合并，如果超过chunk_size则先flush再开新chunk
                        base_content = current_text_chunk.get("content") or ""
                        new_content = f"{base_content}\n{text_content}" if base_content else text_content

                        if chunk_size and chunk_size > 0 and len(new_content) > chunk_size:
                            _flush_current_text_chunk()
                            current_text_chunk = {
                                "content": text_content,
                                "bbox": item_bbox,
                                "page_idx": item_page_idx,
                            }
                        else:
                            current_text_chunk["content"] = new_content
                            if item_bbox:
                                current_text_chunk.setdefault("bbox", [])
                                current_text_chunk["bbox"].extend(item_bbox)
                            if item_page_idx:
                                current_text_chunk.setdefault("page_idx", [])
                                current_text_chunk["page_idx"].extend(item_page_idx)

                    last_item_is_title = False

            else:
                # 其他类型暂不处理，跳过
                continue

        # 处理最后一个text chunk
        _flush_current_text_chunk()

        # 将文档级 summary 作为单独 chunk 加入，chunk_index=-1
        # if document_summary and document_summary.strip():
        #     merged_chunks.append(
        #         _create_chunk_model(
        #             content=document_summary.strip(),
        #             title="文档摘要",
        #             cur_title="",
        #             parent_title="",
        #             file_path=file_path,
        #             file_id=file_id,
        #             bbox_list=[],
        #             page_idx_list=[0],
        #             bbox_type="text",
        #             chunk_id=_generate_chunk_id(),
        #             chunk_index=-1,
        #             chunk_source=chunk_source,
        #         )
        #     )
        return merged_chunks

    async def parse_pdf(
        self,
        pdf_path: Union[str, Path],
        output_dir: Optional[str] = None,
        method: str = "auto",
        lang: Optional[str] = None,
        chunk_size: Optional[int] = None,
        file_id: Optional[str] = None,
        include_parent_titles=True,
        **kwargs,
    ) -> List[ChunkModel]:
        """
        Parse PDF document using MinerU 2.0

        Args:
            pdf_path: Path to the PDF file
            output_dir: Output directory path
            method: Parsing method (auto, txt, ocr)
            lang: Document language for OCR optimization
            chunk_size: Chunk size limit (number of characters), if None then no limit
            file_id: File ID for ChunkModel, if None then auto-generated
            include_parent_titles: 是否在title和content中拼接上级标题（默认只使用最近标题）
            **kwargs: Additional parameters for mineru command

        Returns:
            List[ChunkModel]: List of ChunkModel objects
        """
        try:
            # Convert to Path object for easier handling
            pdf_path = Path(pdf_path)
            if not pdf_path.exists():
                raise FileNotFoundError(f"PDF file does not exist: {pdf_path}")

            name_without_suff = pdf_path.stem

            # Prepare output directory
            if output_dir:
                base_output_dir = Path(output_dir)
            else:
                current_dir = os.path.dirname(os.path.abspath(__file__))
                base_output_dir = Path(os.path.join(current_dir, "./mineru_output"))

                

            base_output_dir.mkdir(parents=True, exist_ok=True)

            backend = kwargs.get("backend", "")
            title_correction = kwargs.get("title_correction", False)
            if backend.startswith("vlm-"):
                method = "vlm"
                
            await self._run_mineru_api(
                input_path=pdf_path,
                output_dir=base_output_dir,
                method=method,
                lang=lang,
                mineru_api=MineruParser.mineru_api,
                **kwargs,
            )
            
            # Read the generated output files
            content_list, _ = self._read_output_files(
                base_output_dir, name_without_suff, method=method, title_correction=title_correction
            )

            # 后处理:合并chunk并转换为ChunkModel
            if file_id is None:
                file_id = str(uuid.uuid4())
            file_path_str = str(pdf_path)
            chunk_source = kwargs.get("chunk_source", "document")
            return self._post_process_chunks(
                content_list=content_list,
                file_id=file_id,
                chunk_source=chunk_source,
                file_path=file_path_str,
                chunk_size=chunk_size,
                include_parent_titles=include_parent_titles,
            )

        except MineruExecutionError:
            raise
        except Exception as e:
            logging.error(f"Error in parse_pdf: {str(e)}")
            raise

    async def get_summary(self,merged_outputs):
        logging.info(f"[MinerU] Starting to generate summaries for TEXT chunks...")

        # 为每个TEXT chunk准备摘要输入（title + text）并创建任务
        summary_tasks = []
        text_chunk_indices = []  # 记录TEXT chunk在merged_outputs中的索引
        for idx, chunk in enumerate(merged_outputs):
            if chunk.bbox_type == "text":
                title = chunk.title.strip()
                text = chunk.content.strip()
                # 组合title和text作为摘要输入
                summary_input = title + "\n" + text if title and text else (title if title else text)
                if summary_input:
                    summary_tasks.append(self.generate_summary(summary_input))
                    text_chunk_indices.append(idx)
        
        # 并发生成摘要
        if summary_tasks:
            try:
                summaries = await asyncio.gather(*summary_tasks)
                
                # 将生成的摘要填充到对应chunk的summary字段
                for idx, summary_text in zip(text_chunk_indices, summaries):
                    merged_outputs[idx].summary = summary_text.strip()
                
                logging.info(f"[MinerU] Generated {len(summaries)} summaries for TEXT chunks.")
                
                return merged_outputs
            except Exception as e:
                logging.error(f"[MinerU] Failed to generate summaries: {e}")

        else:
            logging.info(f"[MinerU] No TEXT chunks with content found, skipping summary generation.")
            return merged_outputs
        
        
    async def generate_document_summary(self, text: str, semaphore=sem) -> str:
        """
        根据所有章节摘要生成整篇文档的摘要（篇章级，总结更全面，字数可更长）。
        """
        async with semaphore:
            system_prompt = f"""
                你是一个专业的文档摘要助手。
                下面给出的是一篇文档的章节标题及对应的章节摘要，请你基于这些信息生成【整篇文档】的总体摘要。

                ## 输入格式：
                每一章使用如下形式给出：
                章节标题
                章节摘要

                多个章节之间用空行分隔。

                ## 输出要求：
                1. 用中文撰写。
                2. 先简要说明整篇文档的主题与目的。
                3. 再概括文档的主要内容框架和关键要点。
                4. 字数控制在 200～400 字之间。
                5. 只输出摘要正文，不要包含“以下是摘要”之类的额外说明。
            """
            response = await async_client.chat.completions.create(
                model=os.getenv("MODEL_NAME"),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text},
                ],
            )
            return response.choices[0].message.content
        
        
    async def get_summary_by_chapter(self, merged_outputs: List[ChunkModel]) -> List[ChunkModel]:
        """
        按“章”（一级标题）对文本 chunk 聚合，并为每一章生成一个摘要 ChunkModel。
        章节标题优先从 others['chapter_title'] 中获取。
        """
        logging.info(f"[MinerU] Starting to generate chapter-level summaries...")

        # 聚合每一章的内容
        chapter_contents: Dict[str, Dict[str, Any]] = {}
        for chunk in merged_outputs:
            if chunk.bbox_type != "text":
                continue
            chapter_title = ""
            if isinstance(chunk.others, dict):
                chapter_title = chunk.others.get("chapter_title") or ""
            if not chapter_title:
                # 兜底：用当前标题或总标题作为章节名
                chapter_title = (chunk.cur_title or chunk.title or "").strip()
            if not chapter_title:
                continue

            if chapter_title not in chapter_contents:
                chapter_contents[chapter_title] = {
                    "texts": [],
                    "first_chunk": chunk,
                }
            text = (chunk.content or "").strip()
            if text:
                chapter_contents[chapter_title]["texts"].append(text)

        if not chapter_contents:
            logging.info("[MinerU] No chapter content found, skipping chapter summary generation.")
            return []

        # 为每一章生成摘要
        summary_tasks = []
        chapter_titles: List[str] = []
        for chapter_title, info in chapter_contents.items():
            texts = info["texts"]
            if not texts:
                continue
            chapter_input = chapter_title + "\n" + "\n\n".join(texts)
            summary_tasks.append(self.generate_summary(chapter_input))
            chapter_titles.append(chapter_title)

        if not summary_tasks:
            logging.info("[MinerU] No chapter texts to summarize.")
            return []

        summaries = await asyncio.gather(*summary_tasks)

        # 构造章节摘要 ChunkModel 列表
        chapter_chunks: List[ChunkModel] = []
        for chapter_title, summary_text in zip(chapter_titles, summaries):
            info = chapter_contents.get(chapter_title)
            if not info:
                continue
            first_chunk: ChunkModel = info["first_chunk"]
            content = (summary_text or "").strip()
            if not content:
                continue

            chapter_chunk = ChunkModel(
                chunk_id=f"chapter_{uuid4().hex}",
                chunk_index=-1,
                content=content,
                file_id=first_chunk.file_id,
                file_path=first_chunk.file_path,
                update_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                bbox_type="chapter_summary",
                title=chapter_title,
                cur_title=chapter_title,
                par_title="",
                summary="",
                media_path="",
                chunk_source=first_chunk.chunk_source,
                bbox=[],
                page_idx=[],
                others={
                    "chapter_title": chapter_title,
                    "chapter_summary": True,
                },
            )
            chapter_chunks.append(chapter_chunk)

        logging.info(f"[MinerU] Generated {len(chapter_chunks)} chapter summaries.")
        return chapter_chunks
    
    async def generate_summary(self, chunk:str, semaphore=sem):
        async with semaphore:
            system_prompt = f"""
                你是一个专业的摘要生成助手，请根据以下要求为文本生成一段摘要：
                ## 需要总结的文本：
                {chunk}
                ## 要求：
                1. 摘要字数要小于 100 个字。
                2. 摘要中仅包含文字和字母，不得出现链接或其他特殊符号。
                3. 直接输出摘要部分，不准输出 `以下是文本的摘要` 等字段
            """
            response = await async_client.chat.completions.create(
                            model=os.getenv("MODEL_NAME"),
                            messages=[
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": chunk}
                            ]
                        )
            summary = response.choices[0].message.content
            # print(summary)

            return summary
        
    async def get_document_summary(self, chapter_chunks: List[ChunkModel]):
        """
        根据所有章节级摘要，生成整篇文档的摘要，
        并将该“全文摘要”作为一个特殊的 ChunkModel 追加到章节摘要列表中。

        参数:
            chapter_chunks: 章节摘要的 ChunkModel 列表（通常来自 get_summary_by_chapter）

        返回:
            文档级摘要、章节摘要 ===> list
        """
        parts: List[str] = []
        first_chunk: Optional[ChunkModel] = None

        for ch in chapter_chunks:
            if not isinstance(ch, ChunkModel):
                continue
            # 只使用章节摘要类型的 chunk
            if getattr(ch, "bbox_type", "") != "chapter_summary":
                continue
            if first_chunk is None:
                first_chunk = ch
            title = (ch.title or "").strip()
            content = (ch.content or "").strip()
            if not content:
                continue
            if title:
                parts.append(f"{title}\n{content}")
            else:
                parts.append(content)

        if not parts:
            return []

        doc_input = "\n\n".join(parts)
        doc_summary = await self.generate_document_summary(doc_input)

        # 同时把全文摘要以一个特殊的 ChunkModel 形式，加入到章节摘要 list 中
        if first_chunk is not None:
            full_chunk = ChunkModel(
                chunk_id=f"document_{uuid4().hex}",
                chunk_index=-1,
                content=doc_summary.strip(),
                file_id=first_chunk.file_id,
                file_path=first_chunk.file_path,
                update_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                bbox_type="document_summary",
                title="全文摘要",
                cur_title="全文摘要",
                par_title="",
                summary="",
                media_path="",
                chunk_source=first_chunk.chunk_source,
                bbox=[],
                page_idx=[],
                others={
                    "document_summary": True,
                },
            )
            chapter_chunks.append(full_chunk)

        # return doc_summary
        return chapter_chunks
    
    
    async def convert_image(self, image_path: Union[str, Path], output_dir: Union[str, Path]):
        """Convert image to PNG format using PIL"""
        try:
            # Convert to Path object for easier handling
            image_path = Path(image_path)
            image_name = image_path.stem
            converted_path = os.path.join(output_dir, image_name+".png")
            if not image_path.exists():
                raise FileNotFoundError(f"Image file does not exist: {image_path}")

            # Supported image formats by MinerU 2.0
            mineru_supported_formats = {".png", ".jpeg", ".jpg"}

            # All supported image formats (including those we can convert)
            all_supported_formats = {
                ".png",
                ".jpeg",
                ".jpg",
                ".bmp",
                ".tiff",
                ".tif",
                ".gif",
                ".webp",
            }

            ext = image_path.suffix.lower()
            if ext not in all_supported_formats:
                raise ValueError(
                    f"Unsupported image format: {ext}. Supported formats: {', '.join(all_supported_formats)}"
                )


            # If format is not natively supported by MinerU, convert it
            if ext not in mineru_supported_formats:
                logging.info(
                    f"Converting {ext} image to PNG for MinerU compatibility..."
                )
                try:
                    from PIL import Image
                except ImportError:
                    raise RuntimeError(
                        "PIL/Pillow is required for image format conversion. "
                        "Please install it using: pip install Pillow"
                    )

                try:
                    with Image.open(image_path) as img:
                        # Handle different image modes
                        if img.mode in ("RGBA", "LA", "P"):
                            # For images with transparency or palette, convert to RGB first
                            if img.mode == "P":
                                img = img.convert("RGBA")

                            # Create white background for transparent images
                            background = Image.new("RGB", img.size, (255, 255, 255))
                            if img.mode == "RGBA":
                                background.paste(img, mask=img.split()[-1])  # Use alpha channel as mask
                            else:
                                background.paste(img)
                            img = background
                        elif img.mode not in ("RGB", "L"):
                            # Convert other modes to RGB
                            img = img.convert("RGB")

                        # Save as PNG
                        img.save(converted_path, "PNG", optimize=True)
                        logging.info(
                            f"Successfully converted {image_path} to PNG ({Path(converted_path).stat().st_size / 1024:.1f} KB)"
                        )

                except Exception as e:
                    raise RuntimeError(f"Failed to convert image {image_path}: {str(e)}")
            else:
                # 直接将image_path复制到converted_path
                shutil.copy(image_path, converted_path)
            return converted_path
        
        except Exception as e:
            logging.error(f"Error in convert_image: {str(e)}")
            raise
    
    async def parse_image(
        self,
        image_path: Union[str, Path],
        output_dir: Optional[str] = None,
        lang: Optional[str] = None,
        chunk_size: Optional[int] = None,
        file_id: Optional[str] = None,
        include_parent_titles: bool = False,
        start_page_id = 0,
        end_page_id = 99999,
        **kwargs,
    ) -> List[ChunkModel]:
        """
        Parse image document using MinerU 2.0

        Note: MinerU 2.0 natively supports .png, .jpeg, .jpg formats.
        Other formats (.bmp, .tiff, .tif, etc.) will be automatically converted to .png.

        Args:
            image_path: Path to the image file
            output_dir: Output directory path
            lang: Document language for OCR optimization
            chunk_size: Chunk size limit (number of characters), if None then no limit
            file_id: File ID for ChunkModel, if None then auto-generated
            include_parent_titles: 是否在title和content中拼接上级标题（默认只使用最近标题）
            **kwargs: Additional parameters for mineru command

        Returns:
            List[ChunkModel]: List of ChunkModel objects
        """
        try:
            # Convert to Path object for easier handling
            image_path = Path(image_path)
            if not image_path.exists():
                raise FileNotFoundError(f"Image file does not exist: {image_path}")

            name_without_suff = image_path.stem

            # Prepare output directory
            if output_dir:
                base_output_dir = Path(output_dir)
            else:
                # base_output_dir = image_path.parent / "mineru_output"
                current_dir = os.path.dirname(os.path.abspath(__file__))
                base_output_dir = Path(os.path.join(current_dir, "./mineru_output"))


            base_output_dir.mkdir(parents=True, exist_ok=True)

            try:

                await self._run_mineru_api(
                    input_path=image_path,
                    output_dir=base_output_dir,
                    method="ocr",
                    lang=lang,
                    mineru_api=MineruParser.mineru_api,
                    start_page_id=start_page_id, 
                    end_page_id=end_page_id,
                    **kwargs,
                )

                # Read the generated output files
                content_list, _ = self._read_output_files(
                    base_output_dir, name_without_suff, method="ocr"
                )

                # 后处理:合并chunk并转换为ChunkModel
                if file_id is None:
                    file_id = str(uuid.uuid4())
                file_path_str = str(image_path)
                chunk_source = kwargs.get("chunk_source", "document")
                return self._post_process_chunks(
                    content_list=content_list,
                    file_id=file_id,
                    chunk_source=chunk_source,
                    file_path=file_path_str,
                    chunk_size=chunk_size,
                    include_parent_titles=include_parent_titles,
                )

            except MineruExecutionError:
                raise

        except Exception as e:
            logging.error(f"Error in parse_image: {str(e)}")
            raise


    async def parse_office_doc(
        self,
        doc_path: Union[str, Path],
        output_dir: Optional[str] = None,
        lang: Optional[str] = None,
        chunk_size: Optional[int] = None,
        file_id: Optional[str] = None,
        include_parent_titles: bool = False,
        **kwargs,
    ) -> List[ChunkModel]:
        """
        Parse office document by first converting to PDF, then parsing with MinerU 2.0

        Note: This method requires LibreOffice to be installed separately for PDF conversion.
        MinerU 2.0 no longer includes built-in Office document conversion.

        Supported formats: .doc, .docx, .ppt, .pptx, .xls, .xlsx

        Args:
            doc_path: Path to the document file (.doc, .docx, .ppt, .pptx, .xls, .xlsx)
            output_dir: Output directory path
            lang: Document language for OCR optimization
            chunk_size: Chunk size limit (number of characters), if None then no limit
            file_id: File ID for ChunkModel, if None then auto-generated
            include_parent_titles: 是否在title和content中拼接上级标题（默认只使用最近标题）
            **kwargs: Additional parameters for mineru command

        Returns:
            List[ChunkModel]: List of ChunkModel objects
        """
        try:
            # Convert Office document to PDF using base class method
            pdf_path = self.convert_office_to_pdf(doc_path, output_dir)

            # Parse the converted PDF
            return await self.parse_pdf(
                pdf_path=pdf_path,
                output_dir=output_dir,
                lang=lang,
                chunk_size=chunk_size,
                file_id=file_id,
                include_parent_titles=include_parent_titles,
                **kwargs,
            )

        except Exception as e:
            logging.error(f"Error in parse_office_doc: {str(e)}")
            raise

    async def parse_text_file(
        self,
        text_path: Union[str, Path],
        output_dir: Optional[str] = None,
        lang: Optional[str] = None,
        chunk_size: Optional[int] = None,
        file_id: Optional[str] = None,
        include_parent_titles: bool = False,
        **kwargs,
    ) -> List[ChunkModel]:
        """
        Parse text file by first converting to PDF, then parsing with MinerU 2.0

        Supported formats: .txt, .md

        Args:
            text_path: Path to the text file (.txt, .md)
            output_dir: Output directory path
            lang: Document language for OCR optimization
            chunk_size: Chunk size limit (number of characters), if None then no limit
            file_id: File ID for ChunkModel, if None then auto-generated
            include_parent_titles: 是否在title和content中拼接上级标题（默认只使用最近标题）
            **kwargs: Additional parameters for mineru command

        Returns:
            List[ChunkModel]: List of ChunkModel objects
        """
        try:
            # Convert text file to PDF using base class method
            pdf_path = self.convert_text_to_pdf(text_path, output_dir)
            # print('==========================',pdf_path)
            # Parse the converted PDF
            return await self.parse_pdf(
                pdf_path=pdf_path,
                output_dir=output_dir,
                lang=lang,
                chunk_size=chunk_size,
                file_id=file_id,
                include_parent_titles=include_parent_titles,
                **kwargs,
            )

        except Exception as e:
            logging.error(f"Error in parse_text_file: {str(e)}")
            raise

    
    
    async def parse(
        self,
        file_path: Union[str, Path],
        method: str = "auto",
        output_dir: Optional[str] = None,
        lang: Optional[str] = None,
        chunk_size: Optional[int] = 512,
        file_id: Optional[str] = None,
        summary: bool = True,
        delimiters=None,
        return_chapter_summary: bool = False,
        # include_parent_titles=include_parent_titles,
        **kwargs,
    # ) -> List[ChunkModel]:
    ):
        """
        Parse document using MinerU 2.0 based on file extension

        Args:
            file_path: Path to the file to be parsed
            method: Parsing method (auto, txt, ocr)
            output_dir: Output directory path
            lang: Document language for OCR optimization
            chunk_size: Chunk size limit (number of characters), if None then no limit
            file_id: File ID for ChunkModel, if None then auto-generated
            include_parent_titles: 是否在title和content中拼接上级标题（通过kwargs传递，默认False）
            **kwargs: Additional parameters for mineru command

        Returns:
            List[ChunkModel]: List of ChunkModel objects
            List of chapter summary
        """
        # Convert to Path object
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File does not exist: {file_path}")

        # Get file extension
        ext = file_path.suffix.lower()

        # Choose appropriate parser based on file type
        if ext == ".pdf":
            res = await self.parse_pdf(
                file_path, output_dir, method, lang, chunk_size=chunk_size, file_id=file_id, **kwargs
            )
        elif ext in self.IMAGE_FORMATS:
            res =  await self.parse_image(
                file_path, output_dir, lang, chunk_size=chunk_size, file_id=file_id, **kwargs
            )
        else:
            # For unsupported file types, try as PDF
            logging.warning(
                f"Warning: Unsupported file extension '{ext}', "
                f"attempting to parse as PDF"
            )
            res =  await self.parse_pdf(
                file_path, output_dir, method, lang, chunk_size=chunk_size, file_id=file_id, **kwargs
            )
            
        
        if summary:
            res = await self.get_summary(res)       
        
        if return_chapter_summary:
            chapter_summaries = await self.get_summary_by_chapter(res)
            total_summaries = await self.get_document_summary(chapter_summaries)
            return res, total_summaries
        
        return res,[]

if __name__ == "__main__":
    async def main():      
        doc_parser = MineruParser()
        filepath = "/mnt/ddata2/cc007/omniknow2/parser/rag/parser/test_case/test.docx"
        output_path = "/mnt/ddata2/cc007/omniknow2/parser/rag/tttttt"
        backend = "pipeline"
        vlm_url = "http://127.0.0.1:8406"
        content_list = await doc_parser.parse(
            file_path=filepath,
            # output_dir=output_path,
            chunk_size=1024,
            backend=backend,
            formula=False,
            table=True,
            vlm_url=vlm_url,
        )

        print(content_list)
        print(f"✅ Successfully parsed: {filepath}")
        print(f"📊 Extracted {len(content_list)} content blocks")

    # asyncio.run(main())
         