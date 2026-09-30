# import argparse
# import os
# import re
# import shutil
# import subprocess
# import sys
# import tempfile
# from pathlib import Path
# from typing import List, Optional, Tuple
# def _which_soffice() -> str:
#     for candidate in ("soffice", "libreoffice"):
#         p = shutil.which(candidate)
#         if p:
#             return candidate
#     raise RuntimeError(
#         "未找到 LibreOffice 命令。请确保已安装 LibreOffice，并且命令行可直接运行 `soffice`（或 `libreoffice`）。"
#     )
# _PAGE_RE = re.compile(r"_(\d+)(?:\D*)$", re.IGNORECASE)
# def _sort_exported_pages(export_dir: Path, stem: str) -> List[Path]:
#     pngs = sorted(export_dir.glob(f"{stem}*.png"))
#     if not pngs:
#         # Fallback: LO 可能没有 stem 前缀（通常不会，但做一下容错）
#         pngs = sorted(export_dir.glob("*.png"))
#     def key_fn(p: Path) -> Tuple[int, str]:
#         m = _PAGE_RE.search(p.stem)
#         if m:
#             return int(m.group(1)), p.name
#         # 没有页码时，按文件名排序
#         return 0, p.name
#     # 如果解析出来的页码全是 0，说明没有命名规律可依赖，则按修改时间兜底
#     sorted_by_key = sorted(pngs, key=key_fn)
#     if sorted_by_key and all(key_fn(p)[0] == 0 for p in sorted_by_key):
#         sorted_by_key = sorted(pngs, key=lambda p: p.stat().st_mtime)
#     return sorted_by_key
# def _unique_path(path: Path) -> Path:
#     if not path.exists():
#         return path
#     parent = path.parent
#     stem = path.stem
#     suffix = path.suffix
#     i = 1
#     while True:
#         candidate = parent / f"{stem}_{i}{suffix}"
#         if not candidate.exists():
#             return candidate
#         i += 1
# def export_ppt_pages_to_png(
#     input_path: Path,
#     export_dir: Path,
#     timeout_s: int = 180,
# ) -> None:
#     export_dir.mkdir(parents=True, exist_ok=True)
#     cmd = [
#         _which_soffice(),
#         "--headless",
#         "--nologo",
#         "--nolockcheck",
#         "--convert-to",
#         "png",
#         "--outdir",
#         str(export_dir),
#         str(input_path),
#     ]
#     proc = subprocess.run(
#         cmd,
#         stdout=subprocess.PIPE,
#         stderr=subprocess.PIPE,
#         text=True,
#         timeout=timeout_s,
#     )
#     if proc.returncode != 0:
#         raise RuntimeError(
#             "LibreOffice 导出失败：\n"
#             f"cmd: {' '.join(cmd)}\n"
#             f"returncode: {proc.returncode}\n"
#             f"stderr: {proc.stderr.strip()}\n"
#             f"stdout: {proc.stdout.strip()}"
#         )
# def images_to_pdf(images: List[Path], pdf_path: Path, dpi: int = 200) -> None:
#     # Pillow 只支持通过 save_all/append_images 生成多页 PDF
#     try:
#         from PIL import Image
#     except ImportError as e:
#         raise RuntimeError(
#             "缺少依赖：Pillow。请先安装：pip install Pillow"
#         ) from e
#     pil_images = []
#     try:
#         for img_path in images:
#             img = Image.open(img_path)
#             if img.mode in ("RGBA", "LA"):
#                 # 去掉透明通道，避免某些情况下 PDF 输出报错
#                 bg = Image.new("RGB", img.size, (255, 255, 255))
#                 bg.paste(img, mask=img.split()[-1])
#                 img = bg
#             else:
#                 img = img.convert("RGB")
#             pil_images.append(img)
#         first, rest = pil_images[0], pil_images[1:]
#         first.save(
#             pdf_path,
#             format="PDF",
#             save_all=True,
#             append_images=rest,
#             resolution=dpi,
#         )
#     finally:
#         # 显式释放资源
#         for img in pil_images:
#             try:
#                 img.close()
#             except Exception:
#                 pass
# def convert_one(input_path: Path, outdir: Path, dpi: int, keep_images: bool) -> Path:
#     if input_path.suffix.lower() not in {".ppt", ".pptx"}:
#         raise ValueError(f"不支持的文件类型：{input_path.suffix}，仅支持 .ppt/.pptx")
#     outdir.mkdir(parents=True, exist_ok=True)
#     stem = input_path.stem
#     output_pdf = _unique_path(outdir / f"{stem}.pdf")
#     temp_root = tempfile.TemporaryDirectory()
#     export_dir = Path(temp_root.name) / "export_png"
#     if keep_images:
#         # keep_images 时把导出目录放到 outdir 子目录，方便你查看中间结果
#         export_dir = outdir / f"{stem}_export_png"
#         temp_root.cleanup()  # 取消 TemporaryDirectory 占用
#         temp_root = tempfile.TemporaryDirectory(prefix="ppt_to_pdf_keep_")  # 占位用，不会清理
#         export_dir.mkdir(parents=True, exist_ok=True)
#     try:
#         export_ppt_pages_to_png(input_path=input_path, export_dir=export_dir)
#         pages = _sort_exported_pages(export_dir=export_dir, stem=stem)
#         if not pages:
#             raise RuntimeError(f"在 {export_dir} 中未找到导出的 PNG 页面文件")
#         images_to_pdf(images=pages, pdf_path=output_pdf, dpi=dpi)
#         return output_pdf
#     finally:
#         # 临时目录自动清理；keep_images 时不清理（由用户保留）
#         if not keep_images:
#             temp_root.cleanup()
# def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
#     p = argparse.ArgumentParser(description="PPT/PPTX -> 每页导出为图片 -> 合成多页 PDF")
#     p.add_argument(
#         "--input",
#         "-i",
#         required=True,
#         help="输入 PPT 或 PPTX 文件路径",
#     )
#     p.add_argument(
#         "--outdir",
#         "-o",
#         default=None,
#         help="输出 PDF 目录（默认：输入文件同目录）",
#     )
#     p.add_argument(
#         "--dpi",
#         type=int,
#         default=200,
#         help="PDF 输出 DPI（默认 200）",
#     )
#     p.add_argument(
#         "--keep-images",
#         action="store_true",
#         help="保留 LibreOffice 导出的每页 PNG（默认不保留）",
#     )
#     return p.parse_args(argv)
# def main(argv: Optional[List[str]] = None) -> int:
#     args = parse_args(argv)
#     input_path = Path(args.input)
#     if not input_path.exists():
#         print(f"输入文件不存在：{input_path}", file=sys.stderr)
#         return 2
#     outdir = Path(args.outdir) if args.outdir else input_path.parent
#     pdf_path = convert_one(
#         input_path=input_path,
#         outdir=outdir,
#         dpi=args.dpi,
#         keep_images=bool(args.keep_images),
#     )
#     print(str(pdf_path))
#     return 0

# if __name__ == "__main__":
#     raise SystemExit(main())


# from pptx import Presentation  
# from pptx.enum.shapes import MSO_SHAPE_TYPE  
# from PIL import Image  
# import os  

# def save_slide_as_image(slide, output_folder):  
#     # 获取幻灯片的形状  
#     shapes = slide.shapes  

#     # 遍历形状并保存为图片  
#     for shape in shapes:  
#         if shape.shape_type == MSO_SHAPE_TYPE.TEXT_BOX:  
#             # 对于文本框，先将其文本保存为图片  
#             text = shape.text_frame.text  
#             text_image = Image.new('RGB', (800, 600), (255, 255, 255))  
#             text_image.text((10,10), text)  
#             text_image.save(os.path.join(output_folder, f"text_{shape.id}.png"))  
#         elif shape.shape_type == MSO_SHAPE_TYPE.PICTURE:  
#             # 对于图片，直接保存  
#             shape.image.save(os.path.join(output_folder, f"image_{shape.id}.png"))  
#         # 其他类型的形状可以根据需要处理，如添加到图片上等  

# def export_ppt_to_images(ppt_path, output_folder):  
#     # 加载PPT文件  
#     prs = Presentation(ppt_path)  

#     # 获取PPT中的幻灯片  
#     slides = prs.slides  

#     # 确保输出目录存在  
#     if not os.path.exists(output_folder):  
#         os.makedirs(output_folder)  

#     # 遍历幻灯片，并导出为图片  
#     for i, slide in enumerate(slides):  
#         save_slide_as_image(slide, output_folder)  

# # 使用示例  
# ppt_path = "/data/workspace/gcy/omniknow2/parser/rag/最新A320常见故障快速处理.ppt"  # PPT文件路径  
# output_folder = "/data/workspace/gcy/omniknow2/parser/rag/pptest"  # 输出目录路径  
# export_ppt_to_images(ppt_path, output_folder)


from pptx import Presentation
from pptx.util import Pt

# 先用 LibreOffice 把 .ppt 转成 .pptx，再用这个脚本替换字体
prs = Presentation("/data/workspace/gcy/omniknow2/parser/rag/最新A320常见故障快速处理.pptx")
for slide in prs.slides:
    for shape in slide.shapes:
        if shape.has_text_frame:
            for para in shape.text_frame.paragraphs:
                for run in para.runs:
                    if run.font.name:
                        run.font.name = "宋体"  # 替换为可用字体
prs.save("/data/workspace/gcy/omniknow2/parser/rag/最新A320常见故障快速处理3.pptx")