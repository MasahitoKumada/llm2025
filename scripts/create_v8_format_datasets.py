#!/usr/bin/env python3
"""
v8戦略: フォーマット別データセット作成スクリプト

段階的SFT（Sequential Format Learning）のためのフォーマット別データセットを作成します。

Person Uの知見に基づく:
- フォーマットごとに段階的に学習することで各フォーマットの限界点に到達
- TOMLは他のフォーマットから学習している（Person T発見）
- データ量より質が重要（Person W: 1000件以下で0.8超え）

出力:
- inputs/sft_processed/v8_stage1_json_csv/train.json (JSON/CSV専用)
- inputs/sft_processed/v8_stage2_yaml/train.json (YAML専用)
- inputs/sft_processed/v8_stage3_xml/train.json (XML専用)
- inputs/sft_processed/v8_stage4_mixed/train.json (複合・TOML最終調整用)
- inputs/sft_processed/v8_curated_1k/train.json (高品質1000件)
"""
import json
import re
import csv
import yaml
import io
import xml.etree.ElementTree as ET
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple, Optional, Any
import hashlib

# Python 3.11+ のtomllib、それ以前は tomli
try:
    import tomllib
except ImportError:
    import tomli as tomllib


# ============================================================
# 設定
# ============================================================
INPUT_DIRS = {
    "u10bei_v2": Path("inputs/sft/1-1_512_v2"),
    "u10bei_v4": Path("inputs/sft/1-2_512_v4"),
    "u10bei_v5": Path("inputs/sft/1-3_512_v5"),
    "daichira_3k": Path("inputs/sft/2-1_3k_mix"),
    "daichira_5k": Path("inputs/sft/2-2_5k_mix"),
    "daichira_hard_4k": Path("inputs/sft/2-3_hard_4k"),
}

OUTPUT_DIR = Path("inputs/sft_processed")

# 各Stageの目標件数
STAGE1_TARGET = 800    # JSON/CSV
STAGE2_TARGET = 500    # YAML
STAGE3_TARGET = 500    # XML
STAGE4_TARGET = 1000   # Mixed
CURATED_TARGET = 1000  # 高品質データ


# ============================================================
# バリデーション関数
# ============================================================
def validate_json(text: str) -> Tuple[bool, Optional[str]]:
    """JSONのバリデーション"""
    try:
        if not text.strip():
            return False, "empty"
        obj = json.loads(text)
        if not isinstance(obj, (dict, list)):
            return False, "not_object_or_array"
        return True, None
    except Exception as e:
        return False, str(e)


def validate_csv(text: str) -> Tuple[bool, Optional[str]]:
    """CSVのバリデーション"""
    try:
        if not text.strip():
            return False, "empty"
        reader = csv.reader(io.StringIO(text))
        rows = list(reader)
        if len(rows) < 2:  # ヘッダー + 1行以上
            return False, "insufficient_rows"
        header_len = len(rows[0])
        for i, row in enumerate(rows[1:], 2):
            if len(row) != header_len:
                return False, f"row_{i}_column_mismatch"
        return True, None
    except Exception as e:
        return False, str(e)


def validate_yaml(text: str) -> Tuple[bool, Optional[str]]:
    """YAMLのバリデーション"""
    try:
        if not text.strip():
            return False, "empty"
        obj = yaml.safe_load(text)
        if obj is None:
            return False, "empty_document"
        if not isinstance(obj, (dict, list)):
            return False, "not_mapping_or_sequence"
        return True, None
    except Exception as e:
        return False, str(e)


def validate_xml(text: str) -> Tuple[bool, Optional[str]]:
    """XMLのバリデーション"""
    try:
        if not text.strip():
            return False, "empty"
        ET.fromstring(text)
        return True, None
    except Exception as e:
        return False, str(e)


def validate_toml(text: str) -> Tuple[bool, Optional[str]]:
    """TOMLのバリデーション"""
    try:
        if not text.strip():
            return False, "empty"
        obj = tomllib.loads(text)
        if not isinstance(obj, dict):
            return False, "not_table"
        return True, None
    except Exception as e:
        return False, str(e)


VALIDATORS = {
    "json": validate_json,
    "csv": validate_csv,
    "yaml": validate_yaml,
    "xml": validate_xml,
    "toml": validate_toml,
}


# ============================================================
# ヘルパー関数
# ============================================================
def extract_output_format(sample: Dict) -> Optional[str]:
    """
    サンプルから出力フォーマットを取得します。
    u-10bei系: metadata["format"]
    daichira系: category (C_JSON, C_TOML, etc.)
    """
    # u-10bei系
    if "metadata" in sample and isinstance(sample["metadata"], dict):
        fmt = sample["metadata"].get("format", "").lower()
        if fmt in VALIDATORS:
            return fmt

    # daichira系
    if "category" in sample:
        category = sample["category"]
        if category:
            # "C_JSON" -> "json", "G_TOML" -> "toml"
            match = re.search(r'[CG]_(\w+)', category, re.IGNORECASE)
            if match:
                fmt = match.group(1).lower()
                if fmt in VALIDATORS:
                    return fmt

    return None


def get_assistant_content(sample: Dict) -> Optional[str]:
    """messagesからassistantの回答を取得"""
    messages = sample.get("messages", [])
    for msg in reversed(messages):
        if msg.get("role") == "assistant":
            return msg.get("content", "")
    return None


def extract_structured_output(content: str) -> str:
    """
    assistant回答から構造化データ部分のみを抽出します。
    CoT部分を除去し、純粋な構造化データを返します。
    """
    # Output: などのマーカー以降を抽出
    output_patterns = [
        r'Output:\s*\n',
        r'OUTPUT:\s*\n',
        r'Final:\s*\n',
        r'Answer:\s*\n',
        r'Result:\s*\n',
        r'Response:\s*\n',
    ]

    result = content
    for pattern in output_patterns:
        match = re.search(pattern, result, re.IGNORECASE)
        if match:
            result = result[match.end():]
            break

    # マークダウンコードブロックの除去
    code_block_pattern = r'^```\w*\s*\n?(.*?)```\s*$'
    code_block_match = re.match(code_block_pattern, result.strip(), re.DOTALL)
    if code_block_match:
        result = code_block_match.group(1)

    return result.strip()


def has_unwanted_prefix(content: str) -> bool:
    """不要な前置き文があるかチェック"""
    prefixes = [
        r'^Here\s*(is|are)',
        r'^Sure[,!]?\s*',
        r'^Certainly[,!]?\s*',
        r'^Of course[,!]?\s*',
        r'^I\'ll',
        r'^Let me',
        r'^Below is',
        r'^The following',
    ]
    for pattern in prefixes:
        if re.match(pattern, content.strip(), re.IGNORECASE):
            return True
    return False


def has_markdown_block(content: str) -> bool:
    """マークダウンコードブロックが含まれているかチェック"""
    return bool(re.search(r'```\w*', content))


def validate_sample(sample: Dict, output_format: str) -> Tuple[bool, Optional[str]]:
    """
    サンプルの品質をバリデートします。

    Returns:
        (is_valid, error_reason)
    """
    # assistantコンテンツを取得
    assistant_content = get_assistant_content(sample)
    if not assistant_content:
        return False, "no_assistant_content"

    # 構造化出力を抽出
    structured_output = extract_structured_output(assistant_content)

    # 不要なプレフィックスチェック
    if has_unwanted_prefix(structured_output):
        return False, "unwanted_prefix"

    # マークダウンブロックチェック（構造化出力内に残っている場合）
    if has_markdown_block(structured_output):
        return False, "markdown_block"

    # フォーマット別バリデーション
    validator = VALIDATORS.get(output_format)
    if not validator:
        return False, "unknown_format"

    is_valid, error = validator(structured_output)
    return is_valid, error


def calculate_complexity(sample: Dict, output_format: str) -> int:
    """
    サンプルの複雑さスコアを計算（深さ・要素数など）
    """
    assistant_content = get_assistant_content(sample)
    if not assistant_content:
        return 0

    structured_output = extract_structured_output(assistant_content)

    try:
        if output_format == "json":
            obj = json.loads(structured_output)
            return _calculate_depth(obj)
        elif output_format == "yaml":
            obj = yaml.safe_load(structured_output)
            return _calculate_depth(obj)
        elif output_format == "xml":
            root = ET.fromstring(structured_output)
            return _calculate_xml_depth(root)
        elif output_format == "toml":
            obj = tomllib.loads(structured_output)
            return _calculate_depth(obj)
        elif output_format == "csv":
            reader = csv.reader(io.StringIO(structured_output))
            rows = list(reader)
            return len(rows)
    except:
        pass

    return 0


def _calculate_depth(obj: Any, current_depth: int = 1) -> int:
    """オブジェクトの最大深度を計算"""
    if isinstance(obj, dict):
        if not obj:
            return current_depth
        return max(_calculate_depth(v, current_depth + 1) for v in obj.values())
    elif isinstance(obj, list):
        if not obj:
            return current_depth
        return max(_calculate_depth(item, current_depth + 1) for item in obj)
    return current_depth


def _calculate_xml_depth(element: ET.Element, current_depth: int = 1) -> int:
    """XMLの最大深度を計算"""
    if len(element) == 0:
        return current_depth
    return max(_calculate_xml_depth(child, current_depth + 1) for child in element)


def get_sample_hash(sample: Dict) -> str:
    """重複チェック用のハッシュを生成"""
    content = get_assistant_content(sample) or ""
    return hashlib.sha256(content.encode()).hexdigest()[:16]


# ============================================================
# データローディング
# ============================================================
def load_all_datasets() -> List[Dict]:
    """全データセットをロードして結合"""
    all_samples = []

    for name, path in INPUT_DIRS.items():
        json_path = path / "train.json"
        if json_path.exists():
            print(f"Loading {name} from {json_path}...")
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for sample in data:
                    sample["_source"] = name
                all_samples.extend(data)
                print(f"  Loaded {len(data)} samples")

    print(f"\nTotal samples loaded: {len(all_samples)}")
    return all_samples


# ============================================================
# データセット作成関数
# ============================================================
def create_format_dataset(
    all_samples: List[Dict],
    target_formats: List[str],
    target_count: int,
    output_name: str,
    priority: str = "quality"  # "quality" or "complexity"
) -> List[Dict]:
    """
    特定フォーマット専用のデータセットを作成

    Args:
        all_samples: 全サンプル
        target_formats: 対象フォーマット（例: ["json", "csv"]）
        target_count: 目標件数
        output_name: 出力ディレクトリ名
        priority: 優先順位 ("quality"=バリデーション通過優先, "complexity"=複雑さ優先)
    """
    print(f"\n{'='*60}")
    print(f"Creating {output_name} dataset")
    print(f"Target formats: {target_formats}")
    print(f"Target count: {target_count}")
    print(f"Priority: {priority}")
    print(f"{'='*60}")

    # フォーマットでフィルタリング
    candidates = []
    format_counts = defaultdict(int)

    for sample in all_samples:
        output_format = extract_output_format(sample)
        if output_format in target_formats:
            # バリデーション
            is_valid, error = validate_sample(sample, output_format)
            if is_valid:
                complexity = calculate_complexity(sample, output_format)
                candidates.append({
                    "sample": sample,
                    "format": output_format,
                    "complexity": complexity,
                    "hash": get_sample_hash(sample)
                })
                format_counts[output_format] += 1

    print(f"\nValid candidates by format:")
    for fmt, count in format_counts.items():
        print(f"  {fmt}: {count}")
    print(f"  Total: {len(candidates)}")

    # ソート（priority に基づく）
    if priority == "complexity":
        candidates.sort(key=lambda x: x["complexity"], reverse=True)

    # 重複除去しながら選択
    selected = []
    seen_hashes = set()

    # フォーマット別にバランスよく選択
    format_quotas = {fmt: target_count // len(target_formats) for fmt in target_formats}
    format_selected = defaultdict(int)

    for candidate in candidates:
        if len(selected) >= target_count:
            break

        hash_val = candidate["hash"]
        fmt = candidate["format"]

        if hash_val in seen_hashes:
            continue

        if format_selected[fmt] < format_quotas[fmt]:
            selected.append(candidate["sample"])
            seen_hashes.add(hash_val)
            format_selected[fmt] += 1

    # 残り枠を埋める
    for candidate in candidates:
        if len(selected) >= target_count:
            break

        hash_val = candidate["hash"]
        if hash_val not in seen_hashes:
            selected.append(candidate["sample"])
            seen_hashes.add(hash_val)

    # 結果出力
    print(f"\nSelected samples by format:")
    final_counts = defaultdict(int)
    for sample in selected:
        fmt = extract_output_format(sample)
        final_counts[fmt] += 1
    for fmt, count in final_counts.items():
        print(f"  {fmt}: {count}")
    print(f"  Total: {len(selected)}")

    # 保存
    output_path = OUTPUT_DIR / output_name
    output_path.mkdir(parents=True, exist_ok=True)

    output_file = output_path / "train.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(selected, f, ensure_ascii=False, indent=2)

    print(f"\nSaved to: {output_file}")

    return selected


def create_curated_dataset(
    all_samples: List[Dict],
    target_count: int = 1000
) -> List[Dict]:
    """
    高品質1000件データセットを作成（Person Wスタイル）

    選択基準:
    1. 全フォーマットのバリデーション100%通過
    2. 不要なプレフィックス/コードブロックなし
    3. 適度な複雑さ（極端に単純/複雑でない）
    4. conversion タスク優先
    """
    print(f"\n{'='*60}")
    print("Creating curated high-quality dataset (Person W style)")
    print(f"Target count: {target_count}")
    print(f"{'='*60}")

    candidates = []

    for sample in all_samples:
        output_format = extract_output_format(sample)
        if not output_format:
            continue

        # バリデーション
        is_valid, error = validate_sample(sample, output_format)
        if not is_valid:
            continue

        complexity = calculate_complexity(sample, output_format)

        # 極端な複雑さを除外（depth 1-6 のみ）
        if complexity < 1 or complexity > 6:
            continue

        # タスクタイプを取得（conversion優先）
        task_type = "unknown"
        if "metadata" in sample and isinstance(sample["metadata"], dict):
            task_type = sample["metadata"].get("type", "unknown")
        elif "task" in sample:
            if "to" in sample["task"].lower():
                task_type = "conversion"
            else:
                task_type = "generation"

        # スコアリング
        score = complexity
        if task_type == "conversion":
            score += 2  # conversion タスクにボーナス

        candidates.append({
            "sample": sample,
            "format": output_format,
            "complexity": complexity,
            "task_type": task_type,
            "score": score,
            "hash": get_sample_hash(sample)
        })

    print(f"\nValid candidates: {len(candidates)}")

    # スコア順でソート
    candidates.sort(key=lambda x: x["score"], reverse=True)

    # フォーマットバランスを考慮して選択
    # 全5フォーマット × 200件 = 1000件 目標
    format_quotas = {"json": 200, "csv": 200, "yaml": 200, "xml": 200, "toml": 200}
    format_selected = defaultdict(int)
    selected = []
    seen_hashes = set()

    # 1st pass: フォーマットバランスを保ちながら選択
    for candidate in candidates:
        if len(selected) >= target_count:
            break

        hash_val = candidate["hash"]
        fmt = candidate["format"]

        if hash_val in seen_hashes:
            continue

        if format_selected[fmt] < format_quotas[fmt]:
            selected.append(candidate["sample"])
            seen_hashes.add(hash_val)
            format_selected[fmt] += 1

    # 2nd pass: 残り枠を埋める
    for candidate in candidates:
        if len(selected) >= target_count:
            break

        hash_val = candidate["hash"]
        if hash_val not in seen_hashes:
            selected.append(candidate["sample"])
            seen_hashes.add(hash_val)

    # 結果出力
    print(f"\nSelected samples by format:")
    final_counts = defaultdict(int)
    task_counts = defaultdict(int)
    for sample in selected:
        fmt = extract_output_format(sample)
        final_counts[fmt] += 1
        # task type
        if "metadata" in sample and isinstance(sample["metadata"], dict):
            task_counts[sample["metadata"].get("type", "unknown")] += 1

    for fmt, count in sorted(final_counts.items()):
        print(f"  {fmt}: {count}")
    print(f"  Total: {len(selected)}")
    print(f"\nTask type distribution:")
    for task, count in sorted(task_counts.items()):
        print(f"  {task}: {count}")

    # 保存
    output_path = OUTPUT_DIR / "v8_curated_1k"
    output_path.mkdir(parents=True, exist_ok=True)

    output_file = output_path / "train.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(selected, f, ensure_ascii=False, indent=2)

    print(f"\nSaved to: {output_file}")

    return selected


# ============================================================
# メイン処理
# ============================================================
def main():
    print("="*60)
    print("v8 Strategy: Format-specific Dataset Creation")
    print("="*60)

    # 全データセットをロード
    all_samples = load_all_datasets()

    # Stage 1: JSON/CSV専用データセット
    create_format_dataset(
        all_samples,
        target_formats=["json", "csv"],
        target_count=STAGE1_TARGET,
        output_name="v8_stage1_json_csv",
        priority="quality"
    )

    # Stage 2: YAML専用データセット
    create_format_dataset(
        all_samples,
        target_formats=["yaml"],
        target_count=STAGE2_TARGET,
        output_name="v8_stage2_yaml",
        priority="complexity"  # 複雑なYAMLを優先
    )

    # Stage 3: XML専用データセット
    create_format_dataset(
        all_samples,
        target_formats=["xml"],
        target_count=STAGE3_TARGET,
        output_name="v8_stage3_xml",
        priority="quality"
    )

    # Stage 4: 複合データセット（TOML最終調整用）
    # Person Tの発見: TOMLは他のフォーマットから学習している
    create_format_dataset(
        all_samples,
        target_formats=["json", "csv", "yaml", "xml", "toml"],
        target_count=STAGE4_TARGET,
        output_name="v8_stage4_mixed",
        priority="complexity"
    )

    # 高品質1000件データセット（Person Wスタイル）
    create_curated_dataset(all_samples, target_count=CURATED_TARGET)

    print("\n" + "="*60)
    print("Dataset creation completed!")
    print("="*60)
    print("\nCreated datasets:")
    print("  - inputs/sft_processed/v8_stage1_json_csv/train.json")
    print("  - inputs/sft_processed/v8_stage2_yaml/train.json")
    print("  - inputs/sft_processed/v8_stage3_xml/train.json")
    print("  - inputs/sft_processed/v8_stage4_mixed/train.json")
    print("  - inputs/sft_processed/v8_curated_1k/train.json")


if __name__ == "__main__":
    main()
