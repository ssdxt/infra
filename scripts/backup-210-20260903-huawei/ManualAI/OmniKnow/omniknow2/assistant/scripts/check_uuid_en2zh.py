import json
from collections import Counter
from pathlib import Path


def load_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def check_duplicate_uuids(data, name: str):
    uuids = [item.get("uuid") for item in data if isinstance(item, dict)]
    counter = Counter(uuids)
    duplicates = [uuid for uuid, cnt in counter.items() if cnt > 1 and uuid is not None]

    if duplicates:
        print(f"[{name}] 发现重复 uuid:")
        for uuid in duplicates:
            print(f"  - {uuid} (重复 {counter[uuid]} 次)")
    else:
        print(f"[{name}] 没有重复 uuid")


def build_uuid_map(data, name: str):
    uuid_map = {}
    for idx, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"[{name}] 第 {idx} 项不是对象: {item}")

        uuid = item.get("uuid")
        if not uuid:
            raise ValueError(f"[{name}] 第 {idx} 项缺少 uuid: {item}")

        if uuid in uuid_map:
            raise ValueError(f"[{name}] 出现重复 uuid: {uuid}")

        uuid_map[uuid] = item

    return uuid_map


def compare_json(original_path: str, translated_path: str):
    original_data = load_json(original_path)
    translated_data = load_json(translated_path)

    if not isinstance(original_data, list):
        raise ValueError("原始 json 顶层不是 list")
    if not isinstance(translated_data, list):
        raise ValueError("翻译后 json 顶层不是 list")

    print("=" * 60)
    print(f"原始文件: {original_path}")
    print(f"翻译文件: {translated_path}")
    print("=" * 60)

    print(f"原始条目数: {len(original_data)}")
    print(f"翻译条目数: {len(translated_data)}")

    check_duplicate_uuids(original_data, "原始 json")
    check_duplicate_uuids(translated_data, "翻译 json")

    original_map = build_uuid_map(original_data, "原始 json")
    translated_map = build_uuid_map(translated_data, "翻译 json")

    original_uuids = set(original_map.keys())
    translated_uuids = set(translated_map.keys())

    missing_in_translated = sorted(original_uuids - translated_uuids)
    extra_in_translated = sorted(translated_uuids - original_uuids)

    print("\n[uuid 集合校验]")
    if not missing_in_translated and not extra_in_translated:
        print("✅ 翻译后的 json 与原始 json 的 uuid 集合完全一致")
    else:
        print("❌ uuid 不一致")

        if missing_in_translated:
            print("\n翻译后缺失的 uuid:")
            for uuid in missing_in_translated:
                item = original_map[uuid]
                print(f"  - uuid={uuid}, original_name={item.get('name')}, type={item.get('type')}")

        if extra_in_translated:
            print("\n翻译后新增的 uuid:")
            for uuid in extra_in_translated:
                item = translated_map[uuid]
                print(f"  - uuid={uuid}, translated_name={item.get('name')}, type={item.get('type')}")

    print("\n[type 一致性校验]")
    type_mismatch = []
    for uuid in sorted(original_uuids & translated_uuids):
        old_type = original_map[uuid].get("type")
        new_type = translated_map[uuid].get("type")
        if old_type != new_type:
            type_mismatch.append((uuid, old_type, new_type))

    if not type_mismatch:
        print("✅ 相同 uuid 的 type 全部一致")
    else:
        print("❌ 存在相同 uuid 但 type 不一致的项:")
        for uuid, old_type, new_type in type_mismatch:
            print(f"  - uuid={uuid}, original_type={old_type}, translated_type={new_type}")

    print("\n[name 变更预览]")
    changed_name_count = 0
    for uuid in sorted(original_uuids & translated_uuids):
        old_name = original_map[uuid].get("name")
        new_name = translated_map[uuid].get("name")
        if old_name != new_name:
            changed_name_count += 1
            print(f"  - uuid={uuid}")
            print(f"    原始: {old_name}")
            print(f"    翻译: {new_name}")

    if changed_name_count == 0:
        print("没有发现 name 变化")
    else:
        print(f"\n共发现 {changed_name_count} 个 name 被翻译/修改")

    print("\n校验完成。")


if __name__ == "__main__":
    # 改成你的实际文件名
    original_json = "children_nodes.json"
    translated_json = "focus_resource.json"

    compare_json(original_json, translated_json)