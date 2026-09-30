import os
import uuid
import json
import logging
import re
from typing import Any

import json_repair

logger = logging.getLogger(__name__)


def steps_to_markdown(state, save_dir=".", filename="report.md"):
    steps = state.get("current_plan", "").steps
    os.makedirs(save_dir, exist_ok=True)

    # id -> step
    step_map = {s.id: s for s in steps}

    # child -> parent
    parent_map = {}
    for s in steps:
        for cid in s.children_ids:
            parent_map[cid] = s.id

    # 计算层级
    def get_level(step_id):
        level = 1
        while step_id in parent_map:
            step_id = parent_map[step_id]
            level += 1
        return level

    md_lines = []
    counters = []

    for i, step in enumerate(steps):
        level = get_level(step.id)

        while len(counters) < level:
            counters.append(0)

        counters = counters[:level]
        counters[level - 1] += 1
        number = ".".join(str(c) for c in counters)
        header = "#" * level
        md_lines.append(f"{header} {number} {step.title}")
        md_lines.append(step.execution_res.strip())

        md_lines.append("")

    markdown_text = "\n".join(md_lines)
    # TODO: 要删掉
    # markdown_text = markdown_text.replace("/mnt/ddata2/cc007/omniknow2/parser/rag/parser/mineru_output", "mineru_output")
    # 保存文件
    path = os.path.join(save_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(markdown_text)

    return path

def flatten_json_tree(tree):
    if "children_ids" in tree[0].keys():
        return tree
    
    flat_nodes = []

    def traverse(node):
        node_id = str(uuid.uuid4())
        children_ids = []
        # 先记录当前节点（保证父节点在前）
        flat_nodes.append({
            "id": node_id,
            "title": node["title"],
            "description": node["description"],
            "step_type": node["step_type"] if "step_type" in node.keys() else "writer",
            "children_ids": children_ids,
        })

        # 再处理 children
        if "children" in node:
            for child in node["children"]:
                child_id = traverse(child)
                children_ids.append(child_id)

        return node_id

    for root in tree:
        traverse(root)

    return flat_nodes


def load_json(data_path):
    """
    # 加载 json 文件
    """
    with open(data_path, encoding="utf-8") as f:
        return json.load(f)


def count_titles(nodes):
    count = 0
    for node in nodes:
        if "title" in node:
            count += 1

        # 递归 children
        if "children" in node:
            count += count_titles(node["children"])

    return count


def sanitize_args(args: Any) -> str:
    """
    Sanitize tool call arguments to prevent special character issues.

    Args:
        args: Tool call arguments string

    Returns:
        str: Sanitized arguments string
    """
    if not isinstance(args, str):
        return ""
    else:
        return (
            args.replace("[", "&#91;")
            .replace("]", "&#93;")
            .replace("{", "&#123;")
            .replace("}", "&#125;")
        )


def _extract_json_from_content(content: str) -> str:
    """
    Extract valid JSON from content that may have extra tokens.
    
    Attempts to find the last valid JSON closing bracket and truncate there.
    Handles both objects {} and arrays [].
    
    Args:
        content: String that may contain JSON with extra tokens
        
    Returns:
        String with potential JSON extracted or original content
    """
    content = content.strip()
    
    # Try to find a complete JSON object or array
    # Look for the last closing brace/bracket that could be valid JSON
    
    # Track counters and whether we've seen opening brackets
    brace_count = 0
    bracket_count = 0
    seen_opening_brace = False
    seen_opening_bracket = False
    in_string = False
    escape_next = False
    last_valid_end = -1
    
    for i, char in enumerate(content):
        if escape_next:
            escape_next = False
            continue
        
        if char == '\\':
            escape_next = True
            continue
        
        if char == '"' and not escape_next:
            in_string = not in_string
            continue
        
        if in_string:
            continue
        
        if char == '{':
            brace_count += 1
            seen_opening_brace = True
        elif char == '}':
            brace_count -= 1
            # Only mark as valid end if we started with opening brace and reached balanced state
            if brace_count == 0 and seen_opening_brace:
                last_valid_end = i
        elif char == '[':
            bracket_count += 1
            seen_opening_bracket = True
        elif char == ']':
            bracket_count -= 1
            # Only mark as valid end if we started with opening bracket and reached balanced state
            if bracket_count == 0 and seen_opening_bracket:
                last_valid_end = i
    
    if last_valid_end > 0:
        truncated = content[:last_valid_end + 1]
        if truncated != content:
            logger.debug(f"Truncated content from {len(content)} to {len(truncated)} chars")
        return truncated
    
    return content


def repair_json_output(content: str) -> str:
    """
    Repair and normalize JSON output.

    Handles:
    - JSON with extra tokens after closing brackets
    - Incomplete JSON structures
    - Malformed JSON from quantized models
    
    Args:
        content (str): String content that may contain JSON

    Returns:
        str: Repaired JSON string, or original content if not JSON
    """
    content = content.strip()
    
    if not content:
        return content

    # First attempt: try to extract valid JSON if there are extra tokens
    content = _extract_json_from_content(content)

    try:
        # Try to repair and parse JSON
        repaired_content = json_repair.loads(content)
        if not isinstance(repaired_content, dict) and not isinstance(
            repaired_content, list
        ):
            logger.warning("Repaired content is not a valid JSON object or array.")
            return content
        content = json.dumps(repaired_content, ensure_ascii=False)
    except Exception as e:
        logger.debug(f"JSON repair failed: {e}")

    return content


def sanitize_tool_response(content: str, max_length: int = 50000) -> str:
    """
    Sanitize tool response to remove extra tokens and invalid content.
    
    This function:
    - Strips whitespace and trailing tokens
    - Truncates excessively long responses
    - Cleans up common garbage patterns
    - Attempts JSON repair for JSON-like responses
    
    Args:
        content: Tool response content
        max_length: Maximum allowed length (default 50000 chars)
        
    Returns:
        Sanitized content string
    """
    if not content:
        return content
    
    content = content.strip()
    
    # First, try to extract valid JSON to remove trailing tokens
    if content.startswith('{') or content.startswith('['):
        content = _extract_json_from_content(content)
    
    # Truncate if too long to prevent token overflow
    if len(content) > max_length:
        logger.warning(f"Tool response truncated from {len(content)} to {max_length} chars")
        content = content[:max_length].rstrip() + "..."
    
    # Remove common garbage patterns that appear from some models
    # These are often seen from quantized models with output corruption
    garbage_patterns = [
        r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F-\x9F]',  # Control characters
    ]
    
    for pattern in garbage_patterns:
        content = re.sub(pattern, '', content)
    
    return content
