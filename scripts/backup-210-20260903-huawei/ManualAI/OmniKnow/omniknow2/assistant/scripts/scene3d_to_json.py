import os
import json
from typing import Any, Dict, List, Tuple


def parse_scene_json(data: Any) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    animation_clip_list: List[Dict[str, Any]] = []
    children_list: List[Dict[str, Any]] = []

    def parse_one_scene(scene: Dict[str, Any]) -> None:
        if not isinstance(scene, dict):
            return

        # 1. 解析 animationClip
        animation_clips = scene.get("animationClip", [])
        if isinstance(animation_clips, list):
            for clip in animation_clips:
                if isinstance(clip, dict):
                    animation_clip_list.append({
                        "name": clip.get("name"),
                        "uuid": clip.get("uuid"),
                    })

        # 2. 递归解析 children
        def walk_children(children: Any) -> None:
            if not isinstance(children, list):
                return

            for node in children:
                if not isinstance(node, dict):
                    continue

                children_list.append({
                    "type": node.get("type"),
                    "name": node.get("name"),
                    "uuid": node.get("uuid"),
                })

                if "children" in node:
                    walk_children(node.get("children"))

        walk_children(scene.get("children", []))

    # 兼容顶层是 dict 或 list
    if isinstance(data, dict):
        parse_one_scene(data)
    elif isinstance(data, list):
        for item in data:
            parse_one_scene(item)
    else:
        raise TypeError(f"Unsupported JSON root type: {type(data).__name__}")

    return animation_clip_list, children_list


if __name__ == "__main__":
    input_file = "/data/workspace/zhangga/omniknow2/assistant/src/subagents/visual3d/resources/hedian_raw/核电 3d.json"
    output_folder = "/data/workspace/zhangga/omniknow2/assistant/src/subagents/visual3d/resources/hedian"

    with open(input_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    animation_clip_list, children_list = parse_scene_json(data)

    p_animation = os.path.join(output_folder, "playAnimation.json")
    p_foucs = os.path.join(output_folder, "focus.json")

    with open(p_animation, "w", encoding="utf-8") as f:
        json.dump(animation_clip_list, f, ensure_ascii=False, indent=2)

    with open(p_foucs, "w", encoding="utf-8") as f:
        json.dump(children_list, f, ensure_ascii=False, indent=2)

    print("✅ 已生成:")
    print(f"{p_animation}, animation clips: {len(animation_clip_list)}")
    print(f"{p_foucs}, children nodes: {len(children_list)}")