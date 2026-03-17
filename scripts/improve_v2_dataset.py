#!/usr/bin/env python3
"""
v2データセット改良スクリプト

Person Cの知見: XMLデータに64/1076件(5.95%)のlintエラーあり
このスクリプトでは:
1. XMLデータのバリデーション
2. エラーデータの除去
3. 改良版データセットの作成
"""

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from collections import Counter
import csv
import io
import re


def load_json(path: str) -> list:
    """JSONファイルを読込む"""
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(data: list, path: str):
    """JSONファイルを保存"""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"保存完了: {path} ({len(data)}件)")


def validate_xml(content: str) -> tuple:
    """XMLをバリデーション"""
    try:
        # XMLヘッダーがない場合は追加してパース
        if not content.strip().startswith('<?xml'):
            content = '<?xml version="1.0"?>' + content
        ET.fromstring(content)
        return True, None
    except ET.ParseError as e:
        return False, str(e)


def validate_json(content: str) -> tuple:
    """JSONをバリデーション"""
    try:
        json.loads(content)
        return True, None
    except json.JSONDecodeError as e:
        return False, str(e)


def validate_yaml(content: str) -> tuple:
    """YAMLをバリデーション（簡易チェック）"""
    # YAMLの基本構文チェック
    try:
        lines = content.strip().split('\n')
        for line in lines:
            # インデントチェック（タブは使用不可）
            if line.startswith('\t'):
                return False, "Tab indentation not allowed in YAML"
        return True, None
    except Exception as e:
        return False, str(e)


def validate_csv(content: str) -> tuple:
    """CSVをバリデーション"""
    try:
        reader = csv.reader(io.StringIO(content))
        rows = list(reader)
        if len(rows) < 1:
            return False, "Empty CSV"
        return True, None
    except csv.Error as e:
        return False, str(e)


def validate_toml(content: str) -> tuple:
    """TOMLをバリデーション（簡易チェック）"""
    try:
        lines = content.strip().split('\n')
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            # セクションヘッダー
            if line.startswith('[') and line.endswith(']'):
                continue
            if line.startswith('[[') and line.endswith(']]'):
                continue
            # キー=値
            if '=' in line:
                continue
        return True, None
    except Exception as e:
        return False, str(e)


def get_output_content(item: dict) -> str:
    """messagesからassistantの出力部分を抽出（Output:以降）"""
    messages = item.get('messages', [])
    for msg in messages:
        if msg.get('role') == 'assistant':
            content = msg.get('content', '')
            # "Output:" 以降を抽出
            if 'Output:' in content:
                output_part = content.split('Output:', 1)[1].strip()
                return output_part
            elif 'Output\n' in content:
                output_part = content.split('Output\n', 1)[1].strip()
                return output_part
            else:
                # Output: がない場合は全体を返す
                return content
    return ''


def validate_data(item: dict) -> tuple:
    """データの品質をバリデーション"""
    metadata = item.get('metadata', {})
    fmt = metadata.get('format', 'unknown')

    # assistantの出力を取得
    output = get_output_content(item)

    if not output.strip():
        return False, "Empty output"

    # フォーマットに応じたバリデーション
    validators = {
        'xml': validate_xml,
        'json': validate_json,
        'yaml': validate_yaml,
        'csv': validate_csv,
        'toml': validate_toml,
    }

    validator = validators.get(fmt)
    if validator:
        return validator(output)

    return True, None


def check_output_quality(item: dict) -> list:
    """出力品質の問題をチェック"""
    issues = []
    output = get_output_content(item)

    # コードフェンスチェック
    if '```' in output:
        issues.append('code_fence')

    # 前置き説明文チェック（Output部分にある場合のみ）
    explanation_patterns = [
        r'^here\s+is',
        r'^here\'s',
        r'^the\s+following',
        r'^below\s+is',
        r'^i\s+will',
        r'^let\s+me',
    ]
    output_lower = output.lower()
    for pattern in explanation_patterns:
        if re.search(pattern, output_lower):
            issues.append('explanation')
            break

    return issues


def analyze_v2_dataset(data: list) -> dict:
    """v2データセットの品質分析"""
    print("=" * 70)
    print("v2データセット品質分析")
    print("=" * 70)

    stats = {
        'total': len(data),
        'by_format': Counter(),
        'by_type': Counter(),
        'validation_errors': Counter(),
        'quality_issues': Counter(),
        'error_indices': [],
        'issue_indices': [],
    }

    for i, item in enumerate(data):
        metadata = item.get('metadata', {})
        fmt = metadata.get('format', 'unknown')
        item_type = metadata.get('type', 'unknown')

        stats['by_format'][fmt] += 1
        stats['by_type'][item_type] += 1

        # バリデーション
        is_valid, error = validate_data(item)
        if not is_valid:
            stats['validation_errors'][fmt] += 1
            stats['error_indices'].append((i, fmt, error))

        # 品質チェック
        issues = check_output_quality(item)
        for issue in issues:
            stats['quality_issues'][issue] += 1
        if issues:
            stats['issue_indices'].append((i, issues))

    # 結果表示
    print(f"\n総件数: {stats['total']}")

    print("\nフォーマット別:")
    for fmt, count in stats['by_format'].most_common():
        error_count = stats['validation_errors'].get(fmt, 0)
        error_rate = error_count / count * 100 if count > 0 else 0
        print(f"  {fmt}: {count}件 (エラー: {error_count}件, {error_rate:.2f}%)")

    print("\nタイプ別:")
    for t, count in stats['by_type'].most_common():
        pct = count / stats['total'] * 100
        print(f"  {t}: {count}件 ({pct:.1f}%)")

    print("\nバリデーションエラー合計:")
    total_errors = sum(stats['validation_errors'].values())
    print(f"  {total_errors}件 ({total_errors / stats['total'] * 100:.2f}%)")

    print("\nバリデーションエラー内訳:")
    for fmt, count in stats['validation_errors'].most_common():
        print(f"  {fmt}: {count}件")

    print("\n品質問題:")
    for issue, count in stats['quality_issues'].most_common():
        print(f"  {issue}: {count}件")

    # エラーサンプルを表示
    if stats['error_indices']:
        print("\nエラーサンプル（最初の5件）:")
        for i, fmt, error in stats['error_indices'][:5]:
            print(f"  [{i}] {fmt}: {error[:80]}...")

    return stats


def create_improved_dataset(
    data: list,
    stats: dict,
    remove_errors: bool = True,
    remove_quality_issues: bool = False
) -> list:
    """改良版データセットを作成"""
    print(f"\n{'=' * 70}")
    print("改良版データセット作成")
    print("=" * 70)

    # 除外するインデックスを収集
    exclude_indices = set()

    if remove_errors:
        for i, fmt, error in stats['error_indices']:
            exclude_indices.add(i)
        print(f"バリデーションエラーを除外: {len(stats['error_indices'])}件")

    if remove_quality_issues:
        for i, issues in stats['issue_indices']:
            exclude_indices.add(i)
        print(f"品質問題を除外: {len(stats['issue_indices'])}件")

    # 重複を除いた除外数
    print(f"総除外数（重複除く）: {len(exclude_indices)}件")

    # フィルタリング
    improved_data = [
        item for i, item in enumerate(data)
        if i not in exclude_indices
    ]

    print(f"改良後データ数: {len(improved_data)}件")
    print(f"除外率: {len(exclude_indices) / len(data) * 100:.2f}%")

    return improved_data


def main():
    """メイン処理"""
    # v2データセット読み込み
    v2_path = "inputs/sft/1-1_512_v2/train.json"
    print(f"読み込み: {v2_path}")
    v2_data = load_json(v2_path)

    # 品質分析
    stats = analyze_v2_dataset(v2_data)

    # 改良版データセット作成（エラーのみ除去）
    improved_data = create_improved_dataset(
        v2_data,
        stats,
        remove_errors=True,
        remove_quality_issues=False
    )

    # 保存
    output_path = "inputs/sft_processed/v3_improved/train.json"
    save_json(improved_data, output_path)

    # 改良後の統計
    print(f"\n{'=' * 70}")
    print("改良後データセット統計")
    print("=" * 70)

    fmt_counts = Counter()
    type_counts = Counter()
    for item in improved_data:
        metadata = item.get('metadata', {})
        fmt_counts[metadata.get('format', 'unknown')] += 1
        type_counts[metadata.get('type', 'unknown')] += 1

    print("\nフォーマット分布:")
    for fmt, count in fmt_counts.most_common():
        pct = count / len(improved_data) * 100
        print(f"  {fmt}: {count}件 ({pct:.1f}%)")

    print("\nタイプ分布:")
    for t, count in type_counts.most_common():
        pct = count / len(improved_data) * 100
        print(f"  {t}: {count}件 ({pct:.1f}%)")


if __name__ == "__main__":
    main()
