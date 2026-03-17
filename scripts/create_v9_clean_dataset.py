#!/usr/bin/env python3
"""
v9 Clean Dataset Creation Script

Person R の Empty Think Injection と Person Y のデータクリーニングを組み合わせた
高品質データセット作成スクリプト。

主な機能:
1. CoT（Approach: ... Output: ...）を完全削除
2. Empty Think Injection（<think>\n</think>\n\n）を先頭に付与
3. コードフェンス、説明文、後書きを除去
4. 構文検証済みデータのみ出力
"""

import json
import re
import csv
import io
import hashlib
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any
import argparse

# 外部ライブラリ（なければインストール）
try:
    import yaml
except ImportError:
    print("pip install pyyaml")
    exit(1)

try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        print("pip install tomli")
        exit(1)

import xml.etree.ElementTree as ET


# ============================================================
# 構文検証関数
# ============================================================

def validate_json(text: str) -> Tuple[bool, Optional[str]]:
    """JSON構文検証"""
    try:
        if not text.strip():
            return False, "Empty output"

        # NaN/Infinity チェック
        def check_constant(x):
            raise ValueError(f"Invalid constant: {x}")

        parsed = json.loads(text, parse_constant=check_constant)

        # トップレベルがobject/arrayか
        if not isinstance(parsed, (dict, list)):
            return False, "Top level must be object or array"

        return True, None
    except Exception as e:
        return False, str(e)


def validate_yaml(text: str) -> Tuple[bool, Optional[str]]:
    """YAML構文検証"""
    try:
        if not text.strip():
            return False, "Empty output"

        parsed = yaml.safe_load(text)

        if parsed is None:
            return False, "Empty document"

        if not isinstance(parsed, (dict, list)):
            return False, "Top level must be mapping or sequence"

        return True, None
    except Exception as e:
        return False, str(e)


def validate_toml(text: str) -> Tuple[bool, Optional[str]]:
    """TOML構文検証"""
    try:
        if not text.strip():
            return False, "Empty output"

        parsed = tomllib.loads(text)

        if not isinstance(parsed, dict):
            return False, "Top level must be table"

        return True, None
    except Exception as e:
        return False, str(e)


def validate_xml(text: str) -> Tuple[bool, Optional[str]]:
    """XML構文検証"""
    try:
        if not text.strip():
            return False, "Empty output"

        # DOCTYPE/ENTITY チェック（セキュリティ）
        if '<!DOCTYPE' in text or '<!ENTITY' in text:
            return False, "DOCTYPE/ENTITY not allowed"

        ET.fromstring(text)
        return True, None
    except Exception as e:
        return False, str(e)


def validate_csv(text: str) -> Tuple[bool, Optional[str]]:
    """CSV構文検証"""
    try:
        if not text.strip():
            return False, "Empty output"

        reader = csv.reader(io.StringIO(text))
        rows = list(reader)

        if len(rows) < 2:
            return False, "Must have header and at least one data row"

        header_len = len(rows[0])
        for i, row in enumerate(rows[1:], 2):
            if len(row) != header_len:
                return False, f"Row {i} has {len(row)} fields, expected {header_len}"

        return True, None
    except Exception as e:
        return False, str(e)


VALIDATORS = {
    'json': validate_json,
    'yaml': validate_yaml,
    'toml': validate_toml,
    'xml': validate_xml,
    'csv': validate_csv,
}


# ============================================================
# CoT除去・クリーニング関数
# ============================================================

def extract_output_from_cot(text: str) -> str:
    """
    CoT形式（Approach: ... Output: ...）から純粋な出力部分を抽出
    """
    # "Output:" 以降を抽出
    output_match = re.search(r'\bOutput:\s*\n?(.*)', text, re.DOTALL | re.IGNORECASE)
    if output_match:
        return output_match.group(1).strip()

    # "Approach:" があるが "Output:" がない場合はスキップ
    if re.search(r'\bApproach:', text, re.IGNORECASE):
        return ""

    # CoTがない場合はそのまま返す
    return text


def clean_output(text: str) -> str:
    """
    出力テキストから不要な要素を除去
    """
    # 1. コードフェンスを除去
    text = re.sub(r'^```\w*\n?', '', text, flags=re.MULTILINE)
    text = re.sub(r'\n?```$', '', text)

    # 2. 説明文プレフィックスを除去
    patterns = [
        r'^Here is.*?:\s*\n?',
        r'^Sure.*?:\s*\n?',
        r'^Certainly.*?:\s*\n?',
        r'^The.*?:\s*\n?',
        r'^Below.*?:\s*\n?',
        r'^I\'ll.*?:\s*\n?',
    ]
    for pattern in patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)

    # 3. 説明文サフィックスを除去
    suffix_patterns = [
        r'\n\nNote:.*$',
        r'\n\nThis.*$',
        r'\n\nPlease.*$',
    ]
    for pattern in suffix_patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.DOTALL)

    return text.strip()


def apply_empty_think_injection(text: str) -> str:
    """
    Empty Think Injection: <think></think> を先頭に付与
    """
    return f"<think>\n</think>\n\n{text}"


# ============================================================
# データ処理メイン
# ============================================================

def get_format_from_u10bei(record: Dict[str, Any]) -> Optional[str]:
    """u-10bei系データからフォーマットを取得"""
    metadata = record.get('metadata', {})
    return metadata.get('format', '').lower()


def get_format_from_daichira(record: Dict[str, Any]) -> Optional[str]:
    """daichira系データからフォーマットを取得"""
    # subcategory: "C_JSON", "C_YAML" など
    subcat = record.get('subcategory', '')
    if subcat.startswith('C_'):
        return subcat[2:].lower()
    return None


def process_u10bei_record(record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """u-10bei系レコードを処理"""
    messages = record.get('messages', [])
    if len(messages) < 2:
        return None

    # フォーマット取得
    fmt = get_format_from_u10bei(record)
    if not fmt or fmt not in VALIDATORS:
        return None

    # assistant出力を取得
    assistant_content = None
    for msg in messages:
        if msg.get('role') == 'assistant':
            assistant_content = msg.get('content', '')
            break

    if not assistant_content:
        return None

    # CoT除去
    clean_content = extract_output_from_cot(assistant_content)
    if not clean_content:
        return None

    # クリーニング
    clean_content = clean_output(clean_content)
    if not clean_content:
        return None

    # 構文検証
    validator = VALIDATORS[fmt]
    is_valid, error = validator(clean_content)
    if not is_valid:
        return None

    # Empty Think Injection適用
    final_content = apply_empty_think_injection(clean_content)

    # 新しいレコードを作成
    new_messages = []
    for msg in messages:
        if msg.get('role') == 'system':
            new_messages.append({
                'role': 'system',
                'content': f"You are a structured data expert. Output only valid {fmt.upper()} without any explanation."
            })
        elif msg.get('role') == 'user':
            new_messages.append(msg.copy())
        elif msg.get('role') == 'assistant':
            new_messages.append({
                'role': 'assistant',
                'content': final_content
            })

    return {
        'messages': new_messages,
        'metadata': {
            'format': fmt,
            'source': record.get('_source', 'u10bei'),
            'original_type': record.get('metadata', {}).get('type', 'unknown'),
        }
    }


def process_daichira_record(record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """daichira系レコードを処理"""
    # フォーマット取得
    fmt = get_format_from_daichira(record)
    if not fmt or fmt not in VALIDATORS:
        return None

    # prompt/chosenを使用
    prompt = record.get('prompt', '')
    chosen = record.get('chosen', '')

    if not prompt or not chosen:
        return None

    # CoT除去
    clean_content = extract_output_from_cot(chosen)
    if not clean_content:
        return None

    # クリーニング
    clean_content = clean_output(clean_content)
    if not clean_content:
        return None

    # 構文検証
    validator = VALIDATORS[fmt]
    is_valid, error = validator(clean_content)
    if not is_valid:
        return None

    # Empty Think Injection適用
    final_content = apply_empty_think_injection(clean_content)

    # 新しいレコードを作成
    return {
        'messages': [
            {
                'role': 'system',
                'content': f"You are a structured data expert. Output only valid {fmt.upper()} without any explanation."
            },
            {
                'role': 'user',
                'content': prompt
            },
            {
                'role': 'assistant',
                'content': final_content
            }
        ],
        'metadata': {
            'format': fmt,
            'source': 'daichira',
            'original_type': record.get('category', 'unknown'),
        }
    }


def deduplicate_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """重複レコードを除去（assistant出力のハッシュベース）"""
    seen_hashes = set()
    unique_records = []

    for record in records:
        # assistant出力を取得
        assistant_content = ''
        for msg in record.get('messages', []):
            if msg.get('role') == 'assistant':
                assistant_content = msg.get('content', '')
                break

        # ハッシュ計算
        content_hash = hashlib.sha256(assistant_content.encode()).hexdigest()

        if content_hash not in seen_hashes:
            seen_hashes.add(content_hash)
            unique_records.append(record)

    return unique_records


def load_and_process_dataset(path: Path, is_u10bei: bool) -> List[Dict[str, Any]]:
    """データセットを読み込んで処理"""
    if not path.exists():
        print(f"  Warning: {path} not found, skipping...")
        return []

    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    processed = []
    for record in data:
        if is_u10bei:
            result = process_u10bei_record(record)
        else:
            result = process_daichira_record(record)

        if result:
            processed.append(result)

    return processed


def main():
    parser = argparse.ArgumentParser(description='Create v9 clean dataset')
    parser.add_argument('--output', type=str, default='inputs/sft_processed/v9/train.json',
                        help='Output file path')
    parser.add_argument('--max-samples', type=int, default=None,
                        help='Maximum samples per format (for testing)')
    args = parser.parse_args()

    # データセットパス
    base_dir = Path('inputs/sft')

    u10bei_datasets = [
        ('1-1_512_v2', True),
        ('1-2_512_v4', True),
        ('1-3_512_v5', True),
        ('1-4_512', True),
        ('1-5_v2', True),
        ('1-6_base', True),
    ]

    daichira_datasets = [
        ('2-1_3k_mix', False),
        ('2-2_5k_mix', False),
        ('2-3_hard_4k', False),
    ]

    all_datasets = u10bei_datasets + daichira_datasets

    # 全レコードを収集
    all_records = []

    print("Loading and processing datasets...")
    for name, is_u10bei in all_datasets:
        path = base_dir / name / 'train.json'
        print(f"  Processing {name}...", end=' ')
        records = load_and_process_dataset(path, is_u10bei)
        print(f"{len(records)} valid records")
        all_records.extend(records)

    print(f"\nTotal records before deduplication: {len(all_records)}")

    # 重複除去
    all_records = deduplicate_records(all_records)
    print(f"Total records after deduplication: {len(all_records)}")

    # フォーマット別統計
    format_counts = {}
    for record in all_records:
        fmt = record.get('metadata', {}).get('format', 'unknown')
        format_counts[fmt] = format_counts.get(fmt, 0) + 1

    print("\nFormat distribution:")
    for fmt, count in sorted(format_counts.items()):
        print(f"  {fmt}: {count}")

    # サンプル数制限（テスト用）
    if args.max_samples:
        limited_records = []
        fmt_counts = {}
        for record in all_records:
            fmt = record.get('metadata', {}).get('format', 'unknown')
            if fmt_counts.get(fmt, 0) < args.max_samples:
                limited_records.append(record)
                fmt_counts[fmt] = fmt_counts.get(fmt, 0) + 1
        all_records = limited_records
        print(f"\nLimited to {args.max_samples} samples per format: {len(all_records)} total")

    # 出力
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(all_records, f, ensure_ascii=False, indent=2)

    print(f"\nSaved to {output_path}")

    # サンプル表示
    print("\n" + "="*60)
    print("Sample output (first record):")
    print("="*60)
    if all_records:
        sample = all_records[0]
        for msg in sample['messages']:
            role = msg['role']
            content = msg['content'][:200] + '...' if len(msg['content']) > 200 else msg['content']
            print(f"\n[{role}]")
            print(content)


if __name__ == '__main__':
    main()
