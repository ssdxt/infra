from __future__ import annotations

from typing import Any

import nlp


def _unescape_delimiter(delimiter: str) -> str:
    return delimiter.replace("\\n", "\n").replace("\\r", "\r").replace("\\t", "\t").replace("\\\\", "\\")


def _iter_sections(markdown_content: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    for line in (markdown_content or "").splitlines():
        text = line.strip()
        if not text:
            continue
        sections.append((text, ""))

    if not sections and markdown_content and markdown_content.strip():
        sections.append((markdown_content.strip(), ""))

    return sections


def _merge_short_sections_by_tokens(
    sections: list[tuple[str, str]],
    min_chunk_token_num: int,
) -> list[tuple[str, str]]:
    """在 section 层面按 token 合并正文，避免后续分块时标题重复。

    约定：
    - 标题行：优先使用 nlp.is_probable_heading_line 判断；layout 中包含 "title"/"head" 也视为标题；
    - 仅合并“正文”行：标题行之间的正文会向后合并，直到 token 数 >= min_chunk_token_num；
    - 标题始终单独成段，不被合并。
    """
    if not sections or min_chunk_token_num <= 0:
        return sections

    merged: list[tuple[str, str]] = []
    buffer_text_parts: list[str] = []

    def flush_buffer() -> None:
        nonlocal buffer_text_parts
        if not buffer_text_parts:
            return
        text = "\n".join(part for part in buffer_text_parts if part)
        if text.strip():
            merged.append((text, ""))
        buffer_text_parts = []

    def is_heading(text: str, layout: str) -> bool:
        if not text or not text.strip():
            return False
        if "title" in layout.lower() or "head" in layout.lower():
            return True
        return nlp.is_probable_heading_line(text)

    for text, layout in sections:
        text = (text or "").strip()
        layout = layout or ""
        if not text:
            continue

        if is_heading(text, layout):
            # 先把之前累计的正文输出，再输出标题本身
            flush_buffer()
            merged.append((text, layout))
            continue

        # 正文：累积到 buffer 中，根据 token 数决定是否“足够长”
        buffer_text_parts.append(text)
        buffer_text = "\n".join(buffer_text_parts)
        if nlp.count_tokens(buffer_text) >= min_chunk_token_num:
            flush_buffer()

    # 收尾：把剩余正文输出
    flush_buffer()
    return merged


def _split_title_and_body(chunk: str) -> tuple[str, str]:
    """尝试把 chunk 拆成 (标题行, 正文)，失败则标题为空。

    仅用于最终合并阶段的标题去重，新的 markdown 专用分块逻辑不依赖此函数。
    """
    if not chunk:
        return "", ""

    lines = [ln for ln in chunk.splitlines() if ln.strip()]
    if not lines:
        return "", ""

    first = lines[0]
    # 直接复用 nlp 的标题判定逻辑
    if nlp.is_probable_heading_line(first):
        body = "\n".join(lines[1:]).strip()
        return first.strip(), body

    return "", "\n".join(lines).strip()


def _merge_short_chunks_markdown(chunks: list[str], min_chunk_token_num: int) -> list[str]:
    """在最终 chunks 上做“最小长度 + 标题去重”的合并。

    规则：
    - 使用 nlp.count_tokens 估算 token 数；
    - 当当前 buffer token 数 < min_chunk_token_num 时，与后一个 chunk 合并；
    - 如果当前 buffer 和下一个 chunk 拥有相同的标题行，只保留一个标题，后续 chunk 只追加正文部分。
    """
    if not chunks or min_chunk_token_num <= 0:
        return chunks

    merged: list[str] = []
    buffer = ""
    buffer_title = ""

    for ck in chunks:
        if not ck or not ck.strip():
            continue

        if not buffer:
            buffer = ck
            buffer_title, _ = _split_title_and_body(ck)
            continue

        if nlp.count_tokens(buffer) < min_chunk_token_num:
            next_title, next_body = _split_title_and_body(ck)

            # 如果标题相同，只拼接正文，避免标题重复
            if buffer_title and next_title and buffer_title == next_title:
                to_add = f"\n{next_body}" if next_body else ""
            else:
                to_add = f"\n{ck}"

            buffer = f"{buffer}{to_add}"
        else:
            merged.append(buffer)
            buffer = ck
            buffer_title, _ = _split_title_and_body(ck)

    if buffer and buffer.strip():
        merged.append(buffer)

    return merged


def chunk_markdown(markdown_content: str, parser_config: dict[str, Any] | None = None) -> list[str]:
    parser_config = parser_config or {}

    delimiter = _unescape_delimiter(str(parser_config.get("delimiter", "\n") or "\n"))
    chunk_token_num = int(parser_config.get("chunk_token_num", 512) or 512)
    overlapped_percent = int(parser_config.get("overlapped_percent", 0) or 0)
    min_chunk_token_num = int(parser_config.get("min_chunk_token_num", 0) or 0)

    sections = _iter_sections(markdown_content)
    if not sections:
        return []

    section_texts = [text for text, _ in sections]
    nlp.remove_contents_table(sections, eng=nlp.is_english(nlp.random_choices(section_texts, k=200)))
    nlp.make_colon_as_title(sections)

    # markdown 专用分块：按标题分组 + token 上下限
    chunks: list[str] = []
    current_lines: list[str] = []

    def flush_current() -> None:
        nonlocal current_lines
        if not current_lines:
            return
        text = "\n".join(current_lines).strip()
        if text:
            chunks.append(text)
        current_lines = []

    def is_heading_line(text: str) -> bool:
        return nlp.is_probable_heading_line(text)

    # 先把 sections 简化为纯文本行序列
    lines: list[str] = []
    for text, _layout in sections:
        text = (text or "").strip()
        if not text:
            continue
        lines.append(text)

    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]

        # 每遇到标题行，先把前一个 chunk 刷出，再以标题开头新建 chunk
        if is_heading_line(line):
            flush_current()
            current_lines.append(line)
            i += 1

            # 吃后续正文，直到达到 min_chunk_token_num 或遇到下一个标题
            while i < n and not is_heading_line(lines[i]):
                trial = "\n".join(current_lines + [lines[i]])
                if min_chunk_token_num > 0 and nlp.count_tokens(trial) < min_chunk_token_num:
                    current_lines.append(lines[i])
                    i += 1
                else:
                    # 已经够长，先看是否会超过 chunk_token_num，如果会，就先刷出当前 chunk
                    if chunk_token_num > 0 and nlp.count_tokens(trial) > chunk_token_num:
                        flush_current()
                        current_lines.append(line)  # 新 chunk 仍然以同一个标题开头
                    else:
                        current_lines.append(lines[i])
                        i += 1
                    break
            continue

        # 非标题行且 current 为空：作为普通正文 chunk 开头
        if not current_lines:
            current_lines.append(line)
            i += 1
            continue

        # 普通正文续写：同时考虑 min_chunk_token_num 和 chunk_token_num
        trial = "\n".join(current_lines + [line])
        tokens = nlp.count_tokens(trial)
        if chunk_token_num > 0 and tokens > chunk_token_num:
            # 当前 chunk 已经足够长，且再加会超上限，先刷出
            flush_current()
            current_lines.append(line)
        else:
            current_lines.append(line)
        i += 1

    flush_current()

    # 兜底：对纯正文 chunk 仍然做一次基于 token 的最小长度合并，避免极短段落
    if min_chunk_token_num > 0:
        chunks = _merge_short_chunks_markdown(chunks, min_chunk_token_num=min_chunk_token_num)

    return chunks
