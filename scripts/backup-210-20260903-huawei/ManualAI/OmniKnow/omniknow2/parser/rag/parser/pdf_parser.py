import asyncio
import os
import pymupdf4llm
from loguru import logger

from .markdown_parser import MarkdownParser
from schema import ChunkModel


def get_images_dir():
    """获取当前目录下的 images 目录路径（仅 PDF -> Markdown 使用）"""
    images_dir = os.path.join(os.getcwd(), "images")
    os.makedirs(images_dir, exist_ok=True)
    return images_dir


class PDFParser:

    def __init__(self):
        pass

    async def convert_markdown(self, file_path: str) -> str:
        """
        将PDF转换为Markdown文本
        图片将保存到当前目录的images目录下
        """
        # 获取图片保存目录
        images_dir = get_images_dir()
        
        # 使用pymupdf4llm将PDF转换为Markdown
        md_text = pymupdf4llm.to_markdown(
            doc=file_path,
            write_images=False,
            image_path=images_dir,
            image_format="jpg",
            dpi=300
        )
        
        logger.info(f"PDF转换为Markdown成功！图片保存目录: {images_dir}")
        return md_text

    async def parse(self, file_id, file_path, min_chunk_size=100, chunk_size=512, chunk_overlap=0,delimiters=["\n\n", "\n", "。", "；"],summary=False,**kwargs):
        """
        解析PDF文件并切分成块
        """
        # 转换PDF为Markdown文本
        markdown_text = await self.convert_markdown(file_path)
        markdown_parser = MarkdownParser(
            min_chunk_size=min_chunk_size,
            max_chunk_size=chunk_size,
            overlap_size=chunk_overlap,
            delimiters=delimiters,
        )
        
        return await markdown_parser.parse_into_chunks(file_id=file_id, markdown_text=markdown_text, file_path=file_path),""


async def main():
    file_path = "./test_case/ap1000_test.pdf"
        
    parser = PDFParser()
    
    chunks = await parser.parse(
        file_path=file_path, 
        file_id="15615615",
        chunk_size=512
    )
    print(chunks)


if __name__ == "__main__":
    
    asyncio.run(main())
   