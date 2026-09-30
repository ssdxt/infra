from pathlib import Path
from typing import Any

# 根据你的项目结构调整 import 路径
from book import chunk_markdown
# from general import chunk_markdown


def chunk_md_file(
    md_path: str | Path,
    parser_config: dict[str, Any] | None = None,
) -> list[str]:
    md_path = Path(md_path)
    if not md_path.is_file():
        raise FileNotFoundError(f"Markdown 文件不存在: {md_path}")

    # 读取 markdown 内容
    text = md_path.read_text(encoding="utf-8")

    # 调用现有的 chunk_markdown
    chunks = chunk_markdown(text, parser_config=parser_config)
    return chunks


if __name__ == "__main__":
    md_file = "/mnt/ddata2/cc007/omniknow2/parser/rag/parser/mineru_output/非能动安全先进核电厂ap1000123/auto/非能动安全先进核电厂ap1000123.md"

    # 可以根据需要调整参数
    parser_config = {
        "delimiter": "\n",        # 分段分隔符
        "chunk_token_num": 1024,   # 每个 chunk 目标 token 数
        "overlapped_percent": 1,  # chunk 之间是否重叠（百分比）
        "min_chunk_token_num":128
    }

    chunks = chunk_md_file(md_file, parser_config=parser_config)

    print(f"总共得到 {len(chunks)} 个 chunks\n")

    # 打印前几个示例
    for i, ck in enumerate(chunks[:5], start=1):
        print(f"==== Chunk {i} ====")
        print(ck)
        print()