#!/usr/bin/env python3
"""
後処理パイプライン - 推論結果のクリーニング

DPOモデルの推論結果から、説明文、コードブロック、末尾の注釈を除去し、
クリーンな構造化データのみを抽出します。

■ 主な処理
1. 説明文の除去（"Sure! Here's...", "Here's the...", など）
2. コードブロックの除去（```json, ```yaml, など）
3. 末尾の注釈除去（"Notes:", "Let me know...", など）
4. フォーマット固有の修正

■ 使い方
  python postprocess_inference.py input.json output.json
  python postprocess_inference.py outputs/inference_dpo_v1.json outputs/inference_dpo_v1_cleaned.json

■ 必要なパッケージ
  なし（標準ライブラリのみ）

Author: AI Assistant
"""

import json
import re
import argparse
from typing import Dict, List, Optional


def remove_preamble(text: str) -> str:
    """
    説明文（前置き）を除去する。

    対応パターン:
    - "Sure! Here's..."
    - "Here's the..."
    - "Let me convert..."
    - "I'll convert..."
    - "Below is..."
    など
    """
    # パターン1: 説明文 + コードブロック開始
    # 例: "Sure! Here's the CSV data converted into JSON format:\n\n```json\n..."
    pattern1 = r'^(?:Sure!?\s*)?(?:Here\'s|Below is|I\'ll|Let me|This is).*?(?::\s*\n|format:\s*\n)'
    text = re.sub(pattern1, '', text, flags=re.IGNORECASE | re.DOTALL)

    # パターン2: ">" で始まる引用ブロック
    # 例: "> ✅ Note: ..."
    text = re.sub(r'^>\s*.*?\n+', '', text, flags=re.MULTILINE)

    # パターン3: "---" で区切られたヘッダー部分
    if text.startswith('---'):
        parts = text.split('---', 2)
        if len(parts) >= 3:
            text = parts[2].strip()

    return text.strip()


def remove_code_fence(text: str) -> str:
    """
    コードフェンスを除去する。

    対応パターン:
    - ```json ... ```
    - ```yaml ... ```
    - ```toml ... ```
    - ```xml ... ```
    - ```csv ... ```
    - ``` ... ``` (言語指定なし)
    """
    text = text.strip()

    # パターン1: 完全なコードフェンス（開始と終了あり）
    # 最初のコードブロックのみを抽出
    pattern = r'```\w*\n?(.*?)```'
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()

    # パターン2: 開始タグのみ（閉じタグなし）
    if '```' in text:
        # 開始タグを探す
        start_match = re.search(r'```\w*\n?', text)
        if start_match:
            return text[start_match.end():].strip()

    return text


def remove_postscript(text: str) -> str:
    """
    末尾の注釈やコメントを除去する。

    対応パターン:
    - "Notes: ..."
    - "### Notes: ..."
    - "Let me know if..."
    - "This JSON is valid..."
    - "✅ This..."
    - "---" 以降の説明
    """
    # パターン1: "Notes:" で始まる段落（### ありなし両対応）
    text = re.sub(r'\n+(?:###?\s*)?Notes?:.*$', '', text, flags=re.IGNORECASE | re.DOTALL)

    # パターン2: "Let me know if..." で始まる文
    text = re.sub(r'\n+Let me know if.*$', '', text, flags=re.IGNORECASE | re.DOTALL)

    # パターン3: "This is a valid..." や "This JSON is..." で始まる文
    text = re.sub(r'\n+This (?:is a valid|JSON|YAML|XML|TOML|CSV).*$', '', text, flags=re.IGNORECASE | re.DOTALL)

    # パターン4: "✅ This..." で始まる文
    text = re.sub(r'\n+[✅✓>]\s*This.*$', '', text, flags=re.IGNORECASE | re.DOTALL)

    # パターン5: "---" 以降の説明（複数の"---"がある場合は最後の1つ）
    if '\n---\n' in text:
        parts = text.rsplit('\n---\n', 1)
        # データ部分が構造化データっぽいかチェック
        if parts[0].strip():
            first_char = parts[0].strip()[0]
            if first_char in '{[<' or parts[0].strip().startswith('<?xml'):
                text = parts[0].strip()

    # パターン6: "### How It Was Converted:" などの説明
    text = re.sub(r'\n+###?\s*(?:How|What|Why).*$', '', text, flags=re.IGNORECASE | re.DOTALL)

    # パターン7: 🔍 などの絵文字で始まる行
    text = re.sub(r'\n+[🔍📝📦🐾🚀]\s*.*$', '', text, flags=re.DOTALL)

    return text.strip()


def extract_structured_data(text: str) -> str:
    """
    テキストから構造化データ部分を抽出する。

    説明文やコードブロックが混在している場合でも、
    JSON/YAML/XML/TOML/CSV の実データ部分を特定して抽出する。
    """
    text = text.strip()

    # JSON/YAML/XMLの開始を検出
    data_start_patterns = [
        (r'\{', 'json_object'),       # JSON object
        (r'\[', 'json_array'),        # JSON array
        (r'<\?xml', 'xml_declaration'), # XML declaration
        (r'<\w+', 'xml_element'),     # XML element
        (r'^\w+\s*:', 'yaml'),        # YAML key
        (r'^\[[\w-]+\]', 'toml'),     # TOML section
        (r'^\w+\s*=', 'toml_or_csv'), # TOML key-value or CSV header
    ]

    # 最も早く見つかったデータ開始位置を特定
    earliest_pos = len(text)
    earliest_type = None

    for pattern, dtype in data_start_patterns:
        match = re.search(pattern, text, re.MULTILINE)
        if match and match.start() < earliest_pos:
            earliest_pos = match.start()
            earliest_type = dtype

    if earliest_pos < len(text):
        # データ開始位置から抽出
        extracted = text[earliest_pos:].strip()
        return extracted

    return text


def clean_generation(text: str) -> str:
    """
    推論結果のクリーニングを行うメイン関数。

    処理順序:
    1. 説明文（前置き）の除去
    2. コードフェンスの除去
    3. 末尾の注釈除去
    4. 構造化データの抽出（フォールバック）
    """
    if not text or not text.strip():
        return text

    original = text

    # Step 1: 説明文の除去
    text = remove_preamble(text)

    # Step 2: コードフェンスの除去
    text = remove_code_fence(text)

    # Step 3: 末尾の注釈除去
    text = remove_postscript(text)

    # Step 4: まだ説明文が残っている場合は、構造化データを抽出
    if text.strip() and not text.strip()[0] in '{[<':
        # YAML/TOML/CSV の場合はそのまま
        if not re.match(r'^[\w-]+(?:\s*[=:]|\s*\[)', text.strip()):
            text = extract_structured_data(text)

    # 空になってしまった場合は元のテキストから再抽出
    if not text.strip():
        text = extract_structured_data(original)

    return text.strip()


def process_inference_file(input_path: str, output_path: str, verbose: bool = True) -> Dict:
    """
    推論結果ファイル全体を処理する。

    Args:
        input_path: 入力ファイルパス
        output_path: 出力ファイルパス
        verbose: 詳細表示するかどうか

    Returns:
        処理統計情報
    """
    print(f"📂 Loading: {input_path}")
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"   Loaded {len(data)} predictions")

    stats = {
        'total': len(data),
        'modified': 0,
        'unchanged': 0,
        'samples': []
    }

    cleaned_data = []

    for item in data:
        task_id = item.get('task_id', '')
        original = item.get('generation', '')

        # クリーニング実行
        cleaned = clean_generation(original)

        # 変更があったかチェック
        if cleaned != original:
            stats['modified'] += 1
            if len(stats['samples']) < 3 and verbose:
                stats['samples'].append({
                    'task_id': task_id,
                    'original_snippet': original[:100],
                    'cleaned_snippet': cleaned[:100] if cleaned else '(empty)'
                })
        else:
            stats['unchanged'] += 1

        cleaned_data.append({
            'task_id': task_id,
            'generation': cleaned
        })

    # 保存
    print(f"💾 Saving: {output_path}")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(cleaned_data, f, ensure_ascii=False, indent=2)

    # 統計表示
    print("\n" + "=" * 60)
    print("📊 POSTPROCESSING REPORT")
    print("=" * 60)
    print(f"Total:     {stats['total']}")
    print(f"Modified:  {stats['modified']} ({stats['modified']/stats['total']*100:.1f}%)")
    print(f"Unchanged: {stats['unchanged']} ({stats['unchanged']/stats['total']*100:.1f}%)")
    print("=" * 60)

    if verbose and stats['samples']:
        print("\n📝 Sample modifications:")
        for i, sample in enumerate(stats['samples'], 1):
            print(f"\n[{i}] {sample['task_id']}")
            print(f"   Before: {sample['original_snippet']}...")
            print(f"   After:  {sample['cleaned_snippet']}...")

    return stats


def main():
    parser = argparse.ArgumentParser(
        description='後処理パイプライン - 推論結果のクリーニング',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python postprocess_inference.py input.json output.json
  python postprocess_inference.py outputs/inference_dpo_v1.json outputs/inference_dpo_v1_cleaned.json

処理内容:
  1. 説明文の除去（"Sure! Here's..."など）
  2. コードブロックの除去（```json```など）
  3. 末尾の注釈除去（"Notes:"など）
  4. 構造化データの抽出
        """
    )
    parser.add_argument('input_file', help='入力ファイルパス（推論結果JSON）')
    parser.add_argument('output_file', help='出力ファイルパス')
    parser.add_argument('-q', '--quiet', action='store_true',
                        help='詳細表示を抑制')

    args = parser.parse_args()

    print("=" * 60)
    print("🧹 後処理パイプライン")
    print("=" * 60)

    process_inference_file(
        args.input_file,
        args.output_file,
        verbose=not args.quiet
    )

    print("\n✅ 処理完了")


if __name__ == "__main__":
    main()
