from __future__ import annotations
import shutil
# from celery import chunks
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
import time
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

base_url = os.getenv("BASE_URL", "")
api_key = os.getenv("API_KEY", "")
model_name = os.getenv("MODEL_NAME", "")
if not base_url or not api_key:
    raise RuntimeError(
        "Title correction requires TITLE_CORRECTION_BASE_URL and TITLE_CORRECTION_API_KEY "
        "(or BASE_URL and API_KEY) in environment"
    )
    
async_client = AsyncOpenAI(base_url=base_url, api_key=api_key)
client = OpenAI(base_url=base_url, api_key=api_key)

sem = asyncio.Semaphore(int(os.getenv("SEM_CONCURRENT")))

# title summary
summary_page = int(os.getenv("SUMMARY_PAGE_NUM"))
title_len = int(os.getenv("TITLE_LEN"))


title_cor_prompt = """
我有一个文档标题列表，请帮我判断每个标题的级别。  

标题级别定义如下：
- 一级标题: text_level=1
- 二级标题: text_level=2
- 三级标题: text_level=3
- 四级标题: text_level=4
- 五级标题: text_level=5
- 六级标题: text_level=6
- 目录: text_level=1

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
6. 文档摘要内容不超过500字

输出 JSON 格式：

{{
  "document_topic": "文档主题",
  "document_summary": "完整总结（200~400字）"
}}

输入目录：
{}
"""


summary_text_prompt = """
你是一名专业的文档分析助手。

任务：
根据给定的文档正文内容，总结文档主题和核心内容。

要求：
1. 输入是正文片段，可能来自文档前几页。
2. 请基于内容进行整体概括，不要逐段复述。
3. 文档摘要内容不超过500字。

输出 JSON 格式：

{{
  "document_topic": "文档主题",
  "document_summary": "完整总结（200~400字）"
}}

输入正文：
{}
"""

generate_title = """
请基于上下文，为当前{media_name}生成一个简洁标题。

要求：
1. 仅输出一行，不要输出解释。
2. 输出格式必须是：“{media_prefix} + 空格 + 标题内容”。
3. 不要带编号（例如“图1/表2/Figure 3”）。
4. 标题应为名词性短语，不要写成完整句子。
5. 内容简洁清晰，长度控制在 8~20 字。
6. 禁止使用空泛词（如“示意图”“相关内容”“情况分析”）。
7. 仅基于上下文生成，不要编造信息。

上文：
{prev_text}

下文：
{next_text}
{table_hint}
"""

generate_summary = """
    你是一个专业的摘要生成助手，请根据以下要求为文本生成一段摘要：
    ## 需要总结的文本：
    {chunk}
    ## 要求：
    1. 摘要字数要小于 50 个字。
    2. 摘要中仅包含文字和字母，不得出现链接或其他特殊符号。
    3. 直接输出摘要部分，不准输出 `以下是文本的摘要` 等字段
"""

CAPTION_PATTERN = re.compile(
    r"^\s*((图|表|Figure|Fig\.?|Table)\s*[\dA-Za-z一二三四五六七八九十]+([\-\.]\d+)*)\s*[:：]?\s*.*",
    re.IGNORECASE
)

def _replace_pptx_fonts(pptx_path: Path, output_path: Path,
                         old_font_keywords: list = None, new_font: str = "宋体"):
    """替换 .pptx 中的私有/不可用字体为指定字体。"""
    try:
        from pptx import Presentation
    except ImportError:
        raise ImportError("请安装 python-pptx：pip install python-pptx")
 
    prs = Presentation(str(pptx_path))
 
    def should_replace(font_name: str) -> bool:
        if not font_name:
            return False
        if old_font_keywords is None:
            return True
        return any(kw in font_name for kw in old_font_keywords)
 
    for slide in prs.slides:
        for shape in slide.shapes:
            if not shape.has_text_frame:
                continue
            for para in shape.text_frame.paragraphs:
                for run in para.runs:
                    if should_replace(run.font.name):
                        run.font.name = new_font
 
    prs.save(str(output_path))


def _fix_pptx(pptx_path, output_path):
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.util import Pt

    prs = Presentation(str(pptx_path))
    for slide in prs.slides:
        for shape in slide.shapes:
            if not shape.has_text_frame:
                continue
            for para in shape.text_frame.paragraphs:
                for run in para.runs:
                    # 修复白色文字
                    try:
                        if run.font.color.rgb and int(str(run.font.color.rgb), 16) > 0xEEEEEE:
                            run.font.color.rgb = RGBColor(0x33, 0x33, 0x33)
                    except:
                        pass
                    # 修复异常小字号
                    try:
                        if run.font.size and run.font.size <= Pt(2):
                            run.font.size = Pt(16)
                    except:
                        pass
    prs.save(str(output_path))


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
        Convert Office document (.doc, .docx, .ppt, .pptx, .xls, .xlsx, .csv) to PDF.
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
            suffix = doc_path.suffix.lower()

            # Prepare output directory
            if output_dir:
                base_output_dir = Path(output_dir)
            else:
                # base_output_dir = doc_path.parent / "libreoffice_output"
                current_dir = os.path.dirname(os.path.abspath(__file__))
                base_output_dir = Path(os.path.join(current_dir, "./libreoffice_output"))

            base_output_dir.mkdir(parents=True, exist_ok=True)
            commands_to_try = ["libreoffice", "soffice"]

            # Create temporary directory for PDF conversion
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                if suffix == ".ppt":
                    logging.info(f"[PPT] 将 .ppt 转为 .pptx 以便替换字体...")
                    pptx_temp = temp_path / (name_without_suff + ".pptx")

                    for cmd in commands_to_try:
                        try:
                            r = subprocess.run(
                                [cmd, "--headless", "--convert-to", "pptx",
                                "--outdir", str(temp_path), str(doc_path)],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300,
                            )
                            if r.returncode == 0:
                                break
                        except (FileNotFoundError, subprocess.TimeoutExpired):
                            continue
                        
                    if  not pptx_temp.exists():
                        raise RuntimeError("LibreOffice 将 .ppt 转 .pptx 失败")

                    # 替换私有字体
                    logging.info(f"[PPT] 替换私有字体为宋体...")
                    pptx_fixed = temp_path / (doc_path.stem + "_fixed.pptx")
                    # _replace_pptx_fonts(
                    #     pptx_path=pptx_temp,
                    #     output_path=pptx_fixed,
                    #     # new_font="宋体",
                    # )
                    _fix_pptx(
                        pptx_path=pptx_temp,
                        output_path=pptx_fixed,
                    )
                    convert_source = pptx_fixed
    
                else:
                    convert_source = doc_path
                
                # Convert to PDF using LibreOffice
                logging.info(f"Converting {doc_path.name} to PDF using LibreOffice...")

                # Prepare subprocess parameters to hide console window on Windows
                import platform

                # Try LibreOffice commands in order of preference

                conversion_successful = False
                for cmd in commands_to_try:
                    try:
                        if suffix == ".csv":
                            # For CSV files, specify the filter to ensure proper conversion
                            convert_cmd = [
                                cmd,
                                "--headless",
                                "--convert-to",
                                "pdf:calc_pdf_Export", 
                                "--infilter=CSV:44,34,76,1",
                                "--outdir",
                                str(temp_path),
                                str(convert_source),
                            ]
                        else:
                            convert_cmd = [
                                cmd,
                                "--headless",
                                "--convert-to",
                                "pdf",
                                "--outdir",
                                str(temp_path),
                                str(convert_source),
                            ]

                        # Prepare conversion subprocess parameters
                        convert_subprocess_kwargs = {
                            "capture_output": True,
                            "text": True,
                            "timeout": 600,  # 60 second timeout
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
                # pdf_files = list(temp_path.glob("*.pdf"))
                # if not pdf_files:
                #     raise RuntimeError(
                #         f"PDF conversion failed for {doc_path.name} - no PDF file generated. "
                #         f"Please check LibreOffice installation or try manual conversion."
                #     )

                # pdf_path = pdf_files[0]
                # logging.info(
                #     f"Generated PDF: {pdf_path.name} ({pdf_path.stat().st_size} bytes)"
                # )

                # # Validate the generated PDF
                # if pdf_path.stat().st_size < 100:  # Very small file, likely empty
                #     raise RuntimeError(
                #         "Generated PDF appears to be empty or corrupted. "
                #         "Original file may have issues or LibreOffice conversion failed."
                #     )

                # # Copy PDF to final output directory
                # final_pdf_path = base_output_dir / f"{name_without_suff}.pdf"
                # shutil.copy2(pdf_path, final_pdf_path)

                # return str(final_pdf_path)
            

                pdf_temp = temp_path / (convert_source.stem + ".pdf")
                if not pdf_temp.exists():
                    raise RuntimeError(f"转换完成但未找到 PDF：{pdf_temp}")
    
                output_pdf = base_output_dir / (doc_path.stem + ".pdf")
                shutil.move(str(pdf_temp), str(output_pdf))
                logging.info(f"PDF 已生成：{output_pdf}")
                return str(output_pdf)

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

            return str(pdf_path)

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


# 判断是否是标题
def is_toc_line(text: str) -> bool:
    text = text.strip()

    patterns = [
        r"[\.·]{2,}\s*[\(\[]?\d+[\)\]]?\s*$",  # ...... (12)
        r"\(\s*\d+\s*\)\s*$",                  # (12)
        r"\.{1,}\s*\d+\s*$",                   # .16 / ...16
        r"\s+\d+\s*$",                         # 结尾是数字
    ]

    for p in patterns:
        if re.search(p, text):
            return True

    return False

def process_titles(data: List[Dict]) -> List[Dict]:
    new_data = []

    for item in data:
        title = item.get("title", "")

        is_toc = is_toc_line(title)

        if is_toc:
            item["text_level"] = -1
            # print(f"Marked as TOC: {title}")

        new_data.append(item)

    return new_data


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


def _item_page_idx_as_int(page_idx: Any) -> int:
    if page_idx is None:
        return 0
    if isinstance(page_idx, (int, float)):
        return int(page_idx)
    if isinstance(page_idx, list) and page_idx:
        return int(page_idx[0])
    return 0


def _item_bbox_quad(item: Dict[str, Any]) -> List[float]:
    bbox = item.get("bbox")
    if bbox is None:
        return [0.0, 0.0, 0.0, 0.0]
    if isinstance(bbox, list) and len(bbox) == 4 and all(isinstance(x, (int, float)) for x in bbox):
        return [float(x) for x in bbox]
    if isinstance(bbox, list) and bbox and isinstance(bbox[0], list):
        inner = bbox[0]
        if len(inner) >= 4:
            return [float(x) for x in inner[:4]]
    return [0.0, 0.0, 0.0, 0.0]


def _mineru_text_items_to_docling(items: List[Dict[str, Any]], doc_name: str) -> Any:
    """将连续文本类 content_list 条目转为 DoclingDocument，供 HybridChunker 使用（不含 image/table）。"""
    from docling_core.types.doc.base import BoundingBox, Size
    from docling_core.types.doc.document import DoclingDocument, ProvenanceItem
    from docling_core.types.doc.labels import DocItemLabel

    if not items:
        return DoclingDocument(name=doc_name)

    max_page = 0
    for it in items:
        max_page = max(max_page, _item_page_idx_as_int(it.get("page_idx")))
    doc = DoclingDocument(name=doc_name)
    placeholder = Size(width=1000.0, height=1400.0)
    for p in range(max_page + 1):
        doc.add_page(page_no=p + 1, size=placeholder)

    for it in items:
        typ = (it.get("type") or "text").lower()
        sub_type = it.get("sub_type", "")
        page_idx = _item_page_idx_as_int(it.get("page_idx"))
        bbox = _item_bbox_quad(it)
        l, t, r, b = bbox

        if typ == "discarded":
            continue
        if typ in ("header", "footer", "page_number"):
            continue

        def _prov(txt: str) -> ProvenanceItem:
            return ProvenanceItem(
                page_no=int(page_idx) + 1,
                bbox=BoundingBox(l=float(l), t=float(t), r=float(r), b=float(b)),
                charspan=(0, len(txt)),
            )

        if typ == "list":
            raw = it.get("list_items") or []
            lines = [(s.strip() if isinstance(s, str) else str(s)).strip() for s in raw]
            text = "\n".join(x for x in lines if x)
            if not text:
                continue
            doc.add_text(label=DocItemLabel.TEXT, text=text, prov=_prov(text))
            continue

        if typ == "text" or sub_type == "text":
            if sub_type == "text":
                li = it.get("list_items")
                if li:
                    text = "\n".join(li)
                else:
                    text = (it.get("text") or "").strip()
            else:
                text = (it.get("text") or "").strip()
            if not text:
                continue
            tl = it.get("text_level")
            prv = _prov(text)
            if tl is not None and int(tl) >= 1:
                doc.add_heading(text=text, level=int(tl), prov=prv)
            else:
                doc.add_text(label=DocItemLabel.TEXT, text=text, prov=prv)
            continue

    return doc


def _build_docling_hybrid_chunker(max_tokens: int) -> Any:
    from transformers import AutoTokenizer
    from docling.chunking import HybridChunker
    from docling_core.transforms.chunker.tokenizer.huggingface import HuggingFaceTokenizer

    tok_path = os.getenv("EMBEDDING_MODEL_PATH", "/ManualAI/OmniKnow/models/Qwen3-Embedding-0.6B")
    auto_tok = AutoTokenizer.from_pretrained(tok_path, local_files_only=True, trust_remote_code=True)
    tokenizer = HuggingFaceTokenizer(tokenizer=auto_tok, max_tokens=max_tokens)
    return HybridChunker(tokenizer=tokenizer, max_tokens=max_tokens, merge_peers=True)


def _hybrid_chunk_bbox_and_pages(dchunk: Any) -> Tuple[List[Any], List[Any]]:
    bbox_list: List[Any] = []
    pages: List[int] = []
    meta = dchunk.meta
    if not meta or not getattr(meta, "doc_items", None):
        return [], []
    for di in meta.doc_items:
        for p in di.prov or []:
            bb = p.bbox
            bbox_list.append([bb.l, bb.t, bb.r, bb.b])
            pages.append(int(p.page_no) - 1)
    uniq = sorted(set(pages))
    return bbox_list, uniq


def _is_text_segment_item(item: Dict[str, Any]) -> bool:
    if not isinstance(item, dict):
        return False
    ct = (item.get("type") or "").lower()
    if ct == "discarded":
        return False
    if ct in ("image", "table"):
        return False
    st = item.get("sub_type", "")
    if ct == "list":
        return True
    if ct == "text" or st == "text":
        return True
    return False


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


def is_caption(text: str) -> bool:
    if not text:
        return False
    return bool(CAPTION_PATTERN.match(text.strip()))


def ensure_list(x: Union[list, int]) -> List:
    """保证 bbox / page_idx 是 list"""
    if isinstance(x, list) and len(x) > 0 and isinstance(x[0], list):
        return x  # 已经是 [[...], [...]]
    if isinstance(x, list) and all(isinstance(i, int) for i in x):
        return [x]  # [1,2,3,4] -> [[1,2,3,4]]
    return [x]


def ensure_page_list(x: Union[int, List[int]]) -> List[int]:
    if isinstance(x, list):
        return x
    return [x]


def merge_caption_inplace(chunks: List[Dict], window: int = 3) -> List[Dict]:
    to_delete = set()

    for i, chunk in enumerate(chunks):

        if chunk["type"] not in ("table", "image"):
            continue

        caption_key = "table_caption" if chunk["type"] == "table" else "image_caption"

        if chunk.get(caption_key):
            continue

        captions = []
        caption_bboxes = []
        caption_pages = []

        # ===== 向后 =====
        for j in range(1, window + 1):
            idx = i + j
            if idx >= len(chunks):
                break

            nxt = chunks[idx]
            if nxt["type"] != "text":
                break

            text = nxt.get("text", "")
            if is_caption(text):
                captions.append(text.strip())
                caption_bboxes.append(nxt.get("bbox"))
                caption_pages.append(nxt.get("page_idx"))
                to_delete.add(idx)
            else:
                break

        # ===== 向前 =====
        for j in range(1, window + 1):
            idx = i - j
            if idx < 0:
                break

            prv = chunks[idx]
            if prv["type"] != "text":
                break

            text = prv.get("text", "")
            if is_caption(text):
                captions.insert(0, text.strip())
                caption_bboxes.insert(0, prv.get("bbox"))
                caption_pages.insert(0, prv.get("page_idx"))
                to_delete.add(idx)
            else:
                break

        # ===== 写回 =====
        if captions:
            chunk[caption_key] = captions

            # 合并 bbox
            origin_bbox = ensure_list(chunk.get("bbox"))
            chunk["bbox"] = origin_bbox + caption_bboxes

            # 合并 page_idx
            origin_pages = ensure_page_list(chunk.get("page_idx"))
            chunk["page_idx"] = origin_pages + caption_pages

    # 删除被合并的 text
    new_chunks = [
        c for idx, c in enumerate(chunks)
        if idx not in to_delete
    ]

    return new_chunks



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
            "formula_enable": kwargs.get("formula_enable", False),
            "table_enable": kwargs.get("table_enable", True),
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
        st = time.time()
        # 读取 JSON 文件
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 根据正则合并可能被分割开的标题文本（如表格/图片标题）
        data = merge_caption_inplace(data)
        
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

        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": title_cor_prompt.format(titles)}],
            stream=False,
        )

        text_output = response.choices[0].message.content

        # 解析 JSON
        try:
            text_output = filter_json(text_output)
            result = json.loads(text_output)
        except json.JSONDecodeError:
            logging.error("标题修正,解析 JSON 失败，模型输出如下：%s", text_output)
            print("标题修正,解析 JSON 失败，模型输出如下：%s", text_output)
            return


        # 目录处理的text_level设置为-1(正则)
        result = process_titles(result)
        
        
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

        print("======================= 标题修正耗时 =====================",time.time()-st)

        st2 = time.time()
        # 文章总结
        summary_text = ""
        if len(titles) < title_len:
            # 递归提取标题
            def normalize_page_idx(page_idx_value: Any) -> List[Any]:
                if page_idx_value is None:
                    return []
                if isinstance(page_idx_value, list):
                    return page_idx_value
                return [page_idx_value]

            def collect_texts_in_first_pages(obj: Any) -> List[str]:
                texts: List[str] = []
                if isinstance(obj, dict):
                    page_idx_values = normalize_page_idx(obj.get("page_idx"))
                    in_first_pages = any(
                        isinstance(idx, (int, float)) and idx < summary_page for idx in page_idx_values
                    )
                    if in_first_pages:
                        sub_type = obj.get("sub_type", "")
                        if sub_type == "text":
                            list_items = obj.get("list_items") or []
                            joined_text = "\n".join([str(it).strip() for it in list_items if str(it).strip()])
                            if joined_text:
                                texts.append(joined_text)
                        else:
                            text = obj.get("text")
                            if isinstance(text, str) and text.strip():
                                texts.append(text.strip())

                    for value in obj.values():
                        texts.extend(collect_texts_in_first_pages(value))
                elif isinstance(obj, list):
                    for item in obj:
                        texts.extend(collect_texts_in_first_pages(item))
                return texts

            first_pages_texts = collect_texts_in_first_pages(data)
            # print(len())
            merged_text = "\n".join(first_pages_texts).strip()
            print("待总结的字数为:",len(merged_text))
            if merged_text:
                response2 = client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": summary_text_prompt.format(merged_text)}],
                    stream=False,
                )
                text_output2 = response2.choices[0].message.content
                try:
                    text_output2 = filter_json(text_output2)
                    result2 = json.loads(text_output2)
                    summary_text = result2.get("document_summary") or ""
                    if not isinstance(summary_text, str):
                        summary_text = str(summary_text)
                except json.JSONDecodeError:
                    logging.info("文档总结(标题),解析 JSON 失败，模型输出如下：%s", text_output2)
                    print("文档总结(标题),解析 JSON 失败，模型输出如下：%s", text_output2)
                    summary_text = ""
                except Exception as e:
                    logging.info("生成文档摘要时发生异常: %s", e)
                    summary_text = ""
            else:
                logging.info("标题数量不足且前5页未提取到有效 text，跳过摘要生成。")
        else:
            response2 = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": summary_prompt.format("\n".join(title_to_level.keys()))}],
                stream=False,
            )
            text_output2 = response2.choices[0].message.content

            # 解析 JSON 并返回文档级摘要字符串
            try:
                text_output2 = filter_json(text_output2)
                result2 = json.loads(text_output2)
                # 期望结构：
                # {
                #   "document_topic": "...",
                #   "document_summary": "..."
                # }
                summary_text = result2.get("document_summary") or ""
                if not isinstance(summary_text, str):
                    summary_text = str(summary_text)
            except json.JSONDecodeError:
                logging.info("文档总结(前几页),解析 JSON 失败，模型输出如下：%s", text_output2)
                summary_text = ""
            except Exception as e:
                logging.info("生成文档摘要时发生异常: %s", e)
                summary_text = ""
            
        print("======================= summary耗时 =====================",time.time()-st2)
        
        return summary_text

    @staticmethod
    def _read_output_files(
        output_dir: Path, file_stem: str, method: str = "auto", title_correction: bool=False
    ) -> Tuple[List[Dict[str, Any]], str, str]:
        """
        Read the output files generated by mineru

        Args:
            output_dir: Output directory
            file_stem: File name without extension

        Returns:
            Tuple containing (content list JSON, Markdown text)
        """
        st = time.time()
        safe_file_stem = sanitize_filename(file_stem)
        
        # Look for the generated files
        md_file = output_dir / f"{file_stem}.md"
        json_file = output_dir / f"{file_stem}_content_list.json"
        images_base_dir = output_dir  # Base directory for images
        summary: str = ""

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

        print("======================= 解压耗时 =====================",time.time()-st)
        # Read JSON content list
        content_list = []
        if json_file.exists():
            try:
                if title_correction:
                    logging.info(f"标题修正中...")
                    summary = MineruParser.update_title_level(json_file) or ""
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

        return content_list, md_content, summary

    def _post_process_chunks(
        self,
        content_list: List[Dict[str, Any]],
        file_id: str,
        file_path: str,
        chunk_source: str,
        chunk_size: Optional[int] = None,
        include_parent_titles: bool = True,
        title_chunk: bool = True,
        document_summary="",
        hybrid_max_tokens: Optional[int] = None,
    ) -> List[ChunkModel]:
        """
        后处理 chunk：
        - 正文（text / list 等）使用 Docling HybridChunker 按结构与 token 上限切分；
        - 图片、表格仍为独立 chunk（逻辑与原先一致）；
        - title_chunk=True 时遇新标题先清空缓冲区，并维护 title_stack，供图/表 chunk 的标题字段使用；
        - bbox / page_idx 来自 HybridChunk 的 doc_items provenance。
        tokenizer 路径：环境变量 HYBRID_TOKENIZER_DIR（默认 /mnt/ddata2/models/bge-m3）；
        max_tokens：参数 hybrid_max_tokens，或环境变量 HYBRID_CHUNK_MAX_TOKENS，或 chunk_size 的启发值，默认 512。
        """
        if not content_list:
            return []

        max_tok_env = (os.getenv("HYBRID_CHUNK_MAX_TOKENS") or "").strip()
        if hybrid_max_tokens is not None:
            max_tokens = int(hybrid_max_tokens)
        elif max_tok_env:
            max_tokens = int(max_tok_env)
        elif chunk_size is not None and chunk_size > 0:
            max_tokens = max(256, min(int(chunk_size), 8192))
        else:
            max_tokens = 512

        try:
            hybrid_chunker = _build_docling_hybrid_chunker(max_tokens)
        except Exception as e:
            raise RuntimeError(
                "Docling HybridChunker 初始化失败，请安装 docling / docling-core / transformers，"
                "并设置 HYBRID_TOKENIZER_DIR 指向本地 tokenizer。原因: "
                f"{e}"
            ) from e

        merged_chunks: List[ChunkModel] = []
        count = 0
        chunk_index_counter = 0
        doc_basename = os.path.basename(file_path).split(".")[0] if file_path else "doc"

        def _next_chunk_index() -> int:
            nonlocal chunk_index_counter
            idx = chunk_index_counter
            chunk_index_counter += 1
            return idx

        def _generate_chunk_id() -> str:
            nonlocal count
            file_name = os.path.basename(file_path).split(".")[0][:10] if file_path else "chunk"
            chunk_id = f"{file_name}_{uuid4().hex}-{count}"
            count += 1
            return chunk_id

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
        ) -> ChunkModel:
            update_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            return ChunkModel(
                chunk_id=chunk_id,
                chunk_index=chunk_index,
                content=content,
                file_id=file_id,
                file_path=file_path,
                update_time=update_time,
                bbox_type=bbox_type,
                title=title,
                cur_title=cur_title,
                par_title=parent_title,
                summary="",
                media_path=media_path,
                chunk_source=chunk_source,
                bbox=bbox_list,
                page_idx=page_idx_list,
                others=others or {},
            )

        title_stack: Dict[int, str] = {}
        last_title_level: Optional[int] = None
        last_item_is_title: bool = False
        text_buffer: List[Dict[str, Any]] = []

        def _build_title_string() -> str:
            if not title_stack:
                return ""
            levels = sorted(title_stack.keys())
            if not levels:
                return ""
            if include_parent_titles:
                return " > ".join(title_stack[l] for l in levels if title_stack.get(l))
            deepest = max(levels)
            return title_stack.get(deepest, "")

        def _get_current_title() -> str:
            if not title_stack:
                return ""
            levels = sorted(title_stack.keys())
            if not levels:
                return ""
            deepest = max(levels)
            return title_stack.get(deepest, "")

        def _get_parent_title() -> str:
            if not title_stack:
                return ""
            levels = sorted(title_stack.keys())
            if not levels:
                return ""
            if len(levels) <= 1:
                return ""
            deepest = max(levels)
            parent_levels = [l for l in levels if l < deepest]
            if not parent_levels:
                return ""
            parent_level = max(parent_levels)
            return title_stack.get(parent_level, "")

        def _flush_hybrid_text_buffer() -> None:
            nonlocal text_buffer
            if not text_buffer:
                return
            dl_doc = _mineru_text_items_to_docling(text_buffer, doc_basename)
            for dchunk in hybrid_chunker.chunk(dl_doc):
                body = (dchunk.text or "").strip()
                if not body:
                    continue
                bbox_list, page_idx_list = _hybrid_chunk_bbox_and_pages(dchunk)
                # 不用 chunk.meta.headings：HybridChunker 的 headings 往往只有当前小节一行，
                # 不含 MinerU text_level 累积的完整路径。与图/表 chunk 一致，统一用 title_stack。
                if title_chunk:
                    title_str = _build_title_string()
                    cur_title_str = _get_current_title()
                    parent_title_str = _get_parent_title()
                else:
                    title_str, cur_title_str, parent_title_str = "", "", ""
                merged_chunks.append(
                    _create_chunk_model(
                        content=body,
                        title=title_str,
                        cur_title=cur_title_str,
                        parent_title=parent_title_str,
                        bbox_list=bbox_list,
                        page_idx_list=page_idx_list,
                        bbox_type="text",
                        chunk_id=_generate_chunk_id(),
                        chunk_index=_next_chunk_index(),
                        chunk_source=chunk_source,
                    )
                )
            text_buffer = []

        for item in content_list:
            if not isinstance(item, dict):
                continue
            content_type = (item.get("type") or "").lower()
            if content_type == "discarded":
                continue

            sub_type = item.get("sub_type", "")

            if content_type == "image":
                _flush_hybrid_text_buffer()

                img_caption = item.get("image_caption", [])
                img_path = item.get("img_path", "")
                if not img_path and not img_caption:
                    continue

                if isinstance(img_caption, list):
                    img_caption = "\n".join(img_caption) if img_caption else ""
                else:
                    img_caption = str(img_caption) if img_caption else ""

                bbox_list = _normalize_bbox(item.get("bbox"))
                page_idx_list = _normalize_page_idx(item.get("page_idx"))

                if title_chunk:
                    title_str = _build_title_string()
                    cur_title_str = _get_current_title()
                    parent_title_str = _get_parent_title()
                else:
                    title_str, cur_title_str, parent_title_str = "", "", ""

                merged_chunks.append(
                    _create_chunk_model(
                        content=img_caption.strip(),
                        title=title_str,
                        cur_title=cur_title_str,
                        parent_title=parent_title_str,
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
                _flush_hybrid_text_buffer()

                table_body = item.get("table_body", "")
                table_caption = item.get("table_caption", [])
                img_url = item.get("img_path", [])

                if not img_url or not table_body:
                    continue

                if isinstance(table_caption, list):
                    table_caption = "\n".join(table_caption) if table_caption else ""
                else:
                    table_caption = str(table_caption) if table_caption else ""

                table_content = table_caption if table_caption else ""
                table_content = (
                    merged_chunks[-1].content + "（续表）"
                    if table_content == "续表"
                    and merged_chunks
                    and merged_chunks[-1].bbox_type == "table"
                    else table_content
                )
                table_html = table_body if table_body else ""

                bbox_list = _normalize_bbox(item.get("bbox"))
                page_idx_list = _normalize_page_idx(item.get("page_idx"))

                if title_chunk:
                    title_str = _build_title_string()
                    cur_title_str = _get_current_title()
                    parent_title_str = _get_parent_title()
                else:
                    title_str, cur_title_str, parent_title_str = "", "", ""

                merged_chunks.append(
                    _create_chunk_model(
                        content=table_content.strip(),
                        title=title_str,
                        cur_title=cur_title_str,
                        parent_title=parent_title_str,
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

            elif _is_text_segment_item(item):
                text_level = item.get("text_level", 0)
                is_title = bool(
                    title_chunk and text_level is not None and int(text_level) > 0
                )

                if sub_type == "text":
                    li = item.get("list_items")
                    if li:
                        text_content = "\n".join(li)
                    else:
                        text_content = (item.get("text") or "").strip()
                elif content_type == "list":
                    raw = item.get("list_items") or []
                    lines = [
                        (s.strip() if isinstance(s, str) else str(s)).strip() for s in raw
                    ]
                    text_content = "\n".join(x for x in lines if x)
                else:
                    text_content = (item.get("text") or "").strip()

                if not text_content:
                    continue

                if is_title:
                    _flush_hybrid_text_buffer()
                    level = int(text_level)
                    if (
                        last_item_is_title
                        and last_title_level == level
                        and level in title_stack
                    ):
                        title_stack[level] = f"{title_stack[level]} {text_content}"
                    else:
                        title_stack[level] = text_content
                        for k in [x for x in list(title_stack.keys()) if x > level]:
                            title_stack.pop(k, None)
                    last_title_level = level
                    last_item_is_title = True
                else:
                    last_item_is_title = False

                text_buffer.append(item)
            else:
                continue

        _flush_hybrid_text_buffer()

        # 将文档级 summary 作为单独 chunk 加入，chunk_index=-1
        if document_summary and document_summary.strip():
            merged_chunks.append(
                _create_chunk_model(
                    content=document_summary.strip(),
                    title="文档摘要",
                    cur_title="",
                    parent_title="",
                    bbox_list=[],
                    page_idx_list=[0],
                    bbox_type="text",
                    chunk_id=_generate_chunk_id(),
                    chunk_index=-1,
                    chunk_source=chunk_source,
                )
            )
        return merged_chunks

    async def parse_pdf(
        self,
        pdf_path: Union[str, Path],
        output_dir: Optional[str] = None,
        method: str = "auto",
        lang: Optional[str] = None,
        chunk_size: Optional[int] = None,
        file_id: Optional[str] = None,
        include_parent_titles: bool = True,
        title_chunk: bool = True,
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
            
            st = time.time()
            await self._run_mineru_api(
                input_path=pdf_path,
                output_dir=base_output_dir,
                method=method,
                lang=lang,
                mineru_api=MineruParser.mineru_api,
                **kwargs,
            )
            print("======================= mineru耗时 =====================",time.time()-st)
            
            # Read the generated output files
            content_list, _, summary = self._read_output_files(
                base_output_dir,
                name_without_suff,
                method=method,
                title_correction=title_correction,
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
                title_chunk=title_chunk,
                document_summary=summary,
                hybrid_max_tokens=kwargs.get("hybrid_max_tokens"),
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
        
        # 无论是否生成摘要，始终返回原始列表，避免上层收到 None
        return merged_outputs
        
    async def generate_summary(self, chunk:str, semaphore=sem):
        async with semaphore:
            response = await async_client.chat.completions.create(
                            model=model_name,
                            messages=[
                                {"role": "system", "content": generate_summary.format(chunk=chunk)},
                                {"role": "user", "content": chunk}
                            ]
                        )
            summary = response.choices[0].message.content
            # print(summary)

            return summary
        
        
    @staticmethod
    def _chunk_text_for_caption_context(chunk: ChunkModel, max_chars: int = 800) -> str:
        """提取用于 caption 生成的上下文文本。"""
        title = (chunk.title or "").strip()
        content = (chunk.content or "").strip()
        if title and content:
            text = f"{title}\n{content}"
        else:
            text = title or content
        return text[:max_chars].strip()

    @staticmethod
    def _extract_table_tr_excerpt(table_body: str, max_tr_rows: int = 3, max_chars: int = 1000) -> str:
        """从 table_body 中提取前几条 tr，并转成简化文本。"""
        if not table_body:
            return ""
        tr_matches = re.findall(r"<tr[^>]*>.*?</tr>", table_body, flags=re.IGNORECASE | re.DOTALL)
        selected_rows = tr_matches[:max_tr_rows] if tr_matches else []
        source = "\n".join(selected_rows) if selected_rows else table_body
        plain_text = re.sub(r"</tr\s*>", "\n", source, flags=re.IGNORECASE)
        plain_text = re.sub(r"<[^>]+>", " ", plain_text)
        plain_text = "\n".join(line.strip() for line in plain_text.splitlines() if line.strip())
        return plain_text[:max_chars]

    @staticmethod
    def _normalize_generated_caption(raw_caption: str, media_prefix: str) -> str:
        """规范化 caption，确保格式为“图/表 + 内容”（不含编号）。"""
        text = (raw_caption or "").strip()
        if not text:
            return ""
        text = re.sub(r"^[\"'`]+|[\"'`]+$", "", text).strip()
        text = re.sub(
            r"^\s*(图|表)\s*[\dA-Za-z一二三四五六七八九十]+(?:[\-\.]\d+)*\s*[:：\-]?\s*",
            r"\1 ",
            text,
            flags=re.IGNORECASE,
        ).strip()
        if text.startswith("图") or text.startswith("表"):
            return re.sub(r"\s+", " ", text).strip()
        return f"{media_prefix} {text}".strip()

    def _collect_caption_context(
        self,
        chunks: List[ChunkModel],
        target_idx: int,
        window: int = 3,
    ) -> Tuple[List[str], List[str]]:
        """
        收集目标 chunk 前后文（按 chunk 个数计数）。

        - 向前最多扫描 window 个 chunk，向后最多扫描 window 个 chunk
        - table/image 也计入扫描个数，但不使用其内容
        - 其他类型 chunk 会提取其文本作为上下文（若为空则忽略）
        - 所有查找避免越界
        """
        prev_contexts: List[str] = []
        next_contexts: List[str] = []
        media_types = {"table", "image"}

        for step in range(1, window + 1):
            i = target_idx - step
            if i < 0:
                break
            chk = chunks[i]
            if chk.bbox_type in media_types:
                continue
            text = self._chunk_text_for_caption_context(chk)
            if text:
                prev_contexts.append(text)
        prev_contexts.reverse()

        for step in range(1, window + 1):
            j = target_idx + step
            if j >= len(chunks):
                break
            chk = chunks[j]
            if chk.bbox_type in media_types:
                continue
            text = self._chunk_text_for_caption_context(chk)
            if text:
                next_contexts.append(text)

        return prev_contexts, next_contexts

    async def _generate_caption_by_context(
        self,
        target_chunk: ChunkModel,
        prev_contexts: List[str],
        next_contexts: List[str],
        table_excerpt: str = "",
        semaphore=sem,
    ) -> str:
        """基于上下文调用 LLM 生成图/表 caption。"""
        media_prefix = "表" if target_chunk.bbox_type == "table" else "图"
        media_name = "表格" if target_chunk.bbox_type == "table" else "图片"
        prev_text = "\n".join(prev_contexts).strip()
        next_text = "\n".join(next_contexts).strip()
        table_hint = f"\n{media_name}内容片段（仅供参考）：\n{table_excerpt}\n" if table_excerpt else ""

        async with semaphore:
            response = await async_client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "你是一个严谨的图/表 caption 生成助手。"},
                    {"role": "user", "content": generate_title.format(
                                                    media_name=media_name,
                                                    media_prefix=media_prefix,
                                                    prev_text=prev_text,
                                                    next_text=next_text,
                                                    table_hint=table_hint
                                                )},
                ],
            )
        raw_caption = response.choices[0].message.content
        return self._normalize_generated_caption(raw_caption, media_prefix)

    async def _fallback_generate_missing_media_captions(
        self,
        merged_outputs: List[ChunkModel],
        window: int = 3,
        max_tr_rows: int = 3,
        enabled: bool = True,
    ) -> List[ChunkModel]:
        """
        对 table/image 且空 caption 的 chunk 做 LLM 兜底生成。
        必须满足：前向>=1 且后向>=1 的可用上下文，否则跳过。
        """
        if not enabled or not merged_outputs:
            return merged_outputs

        candidate_tasks: List[Tuple[int, asyncio.Task]] = []
        for idx, chunk in enumerate(merged_outputs):
            if chunk.bbox_type not in ("table", "image"):
                continue
            if (chunk.content or "").strip():
                continue
            prev_contexts, next_contexts = self._collect_caption_context(merged_outputs, idx, window=window)
            if len(prev_contexts) < 1 or len(next_contexts) < 1:
                continue
            table_excerpt = ""
            if chunk.bbox_type == "table":
                table_body = (chunk.others or {}).get("table_body", "")
                if isinstance(table_body, str):
                    table_excerpt = self._extract_table_tr_excerpt(table_body, max_tr_rows=max_tr_rows)
            task = asyncio.create_task(
                self._generate_caption_by_context(
                    target_chunk=chunk,
                    prev_contexts=prev_contexts,
                    next_contexts=next_contexts,
                    table_excerpt=table_excerpt,
                )
            )
            candidate_tasks.append((idx, task))

        if not candidate_tasks:
            return merged_outputs

        results = await asyncio.gather(*[t for _, t in candidate_tasks], return_exceptions=True)
        generated_count = 0
        for (idx, _), result in zip(candidate_tasks, results):
            if isinstance(result, Exception):
                logging.warning(f"[MinerU] caption fallback failed at chunk idx={idx}: {result}")
                continue
            caption = (result or "").strip()
            if caption:
                merged_outputs[idx].content = caption
                generated_count += 1
        if generated_count:
            logging.info(f"[MinerU] Generated {generated_count} fallback captions for media chunks.")
        return merged_outputs
    
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

                # Read the generated output files（图片场景不单独返回整体摘要字符串）
                content_list, _, _ = self._read_output_files(
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
                    title_chunk=kwargs.get("title_chunk", True),
                    document_summary="",
                    hybrid_max_tokens=kwargs.get("hybrid_max_tokens"),
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
        title_chunk: bool = True,
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
                title_chunk=title_chunk,
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
        title_chunk: bool = True,
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
                title_chunk=title_chunk,
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
        title_chunk: bool = True,  # 是否按标题分块
        doc_summary: bool = True,  # 是否需要文档摘要（控制是否在 parse_pdf 等处注入文档级摘要 chunk）
        title_correction: bool = True,
        **kwargs,
    ) -> List[ChunkModel]:
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
                file_path,
                output_dir,
                method,
                lang,
                chunk_size=chunk_size,
                file_id=file_id,
                title_chunk=title_chunk,
                # 仅当需要文档摘要时才在内部添加 summary chunk
                title_correction=title_correction,
                **kwargs,
            )
        elif ext in self.IMAGE_FORMATS:
            res = await self.parse_image(
                file_path,
                output_dir,
                lang,
                chunk_size=chunk_size,
                file_id=file_id,
                **kwargs,
            )
        else:
            # For unsupported file types, try as PDF
            logging.warning(
                f"Warning: Unsupported file extension '{ext}', "
                f"attempting to parse as PDF"
            )
            res = await self.parse_pdf(
                file_path,
                output_dir,
                method,
                lang,
                chunk_size=chunk_size,
                file_id=file_id,
                title_chunk=title_chunk,
                **kwargs,
            )

        caption_fallback_enable = kwargs.get("caption_fallback_enable", False)
        caption_context_window = kwargs.get("caption_context_window", 3)
        caption_table_tr_rows = kwargs.get("caption_table_tr_rows", 3)
        res = await self._fallback_generate_missing_media_captions(
            merged_outputs=res,
            window=caption_context_window,
            max_tr_rows=caption_table_tr_rows,
            enabled=caption_fallback_enable,
        )
        
        if summary:
            res = await self.get_summary(res)

        if title_correction:
        # 文档级摘要（如果存在）以 chunk_index = -1 的 ChunkModel 形式包含在列表中，
            return res[:-1],res[-1].content if res and res[-1].content else ""
        return res,""

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
         
