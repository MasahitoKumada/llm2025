#!/usr/bin/env python3
"""
v3戦略最終分析スクリプト

SFTデータセットの正確なタスク分布を分析し、
テストデータとの比較に基づいたv3戦略を提案する。
"""
import json
import re
from collections import defaultdict
from pathlib import Path


def load_json(filepath):
    """JSONファイルを読込む"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def detect_task_type_from_sft(item):
    """SFTデータからタスクタイプを検出する"""
    messages = item.get('messages', [])
    metadata = item.get('metadata', {})

    output_format = metadata.get('format', '').upper()

    # システムプロンプトから出力形式を取得
    for msg in messages:
        if msg.get('role') == 'system':
            content = msg.get('content', '')
            # "expert in TOML format" のようなパターン
            match = re.search(
                r'expert in (\w+) format',
                content, re.IGNORECASE
            )
            if match:
                output_format = match.group(1).upper()
            break

    # ユーザーメッセージから入力形式を検出
    input_format = None
    for msg in messages:
        if msg.get('role') == 'user':
            content = msg.get('content', '')

            # パターン: "Transform this CSV data into TOML"
            match = re.search(
                r'(?:Transform|Convert|Change)\s+(?:this\s+)?(\w+)\s+'
                r'(?:data\s+)?(?:into|to)\s+(\w+)',
                content, re.IGNORECASE
            )
            if match:
                input_format = match.group(1).upper()
                output_format = match.group(2).upper()
                break

            # パターン: "CSV code to YAML code"
            match = re.search(
                r'(\w+)\s+(?:code|data)\s+to\s+(\w+)\s+(?:code|format)',
                content, re.IGNORECASE
            )
            if match:
                input_format = match.group(1).upper()
                output_format = match.group(2).upper()
                break

            # パターン: "into XML format"
            if not input_format:
                match = re.search(
                    r'into\s+(\w+)\s+format',
                    content, re.IGNORECASE
                )
                if match:
                    output_format = match.group(1).upper()
                    # 入力形式を推測
                    for fmt in ['CSV', 'JSON', 'YAML', 'XML', 'TOML', 'TEXT']:
                        if fmt.lower() in content.lower()[:100]:
                            input_format = fmt
                            break

    if input_format and output_format:
        # 標準化
        input_format = normalize_format(input_format)
        output_format = normalize_format(output_format)
        if input_format != output_format:
            return f"{input_format} to {output_format}"

    return "Unknown"


def normalize_format(fmt):
    """フォーマット名を標準化"""
    fmt = fmt.upper()
    if fmt in ['TEXT', 'TXT', 'PLAIN']:
        return 'Text'
    return fmt


def analyze_sft_with_improved_detection():
    """改善されたタスク検出でSFTデータセットを分析"""
    all_task_dist = defaultdict(int)
    dataset_results = []

    # 元のSFTデータセット
    sft_dir = Path("inputs/sft")
    for dataset_dir in sorted(sft_dir.iterdir()):
        if dataset_dir.is_dir():
            train_json = dataset_dir / "train.json"
            if train_json.exists():
                data = load_json(train_json)
                task_dist = defaultdict(int)

                for item in data:
                    task_type = detect_task_type_from_sft(item)
                    task_dist[task_type] += 1
                    all_task_dist[task_type] += 1

                dataset_results.append({
                    'name': f"sft/{dataset_dir.name}",
                    'total': len(data),
                    'task_dist': dict(task_dist)
                })

    # 加工済みSFTデータセット
    processed_dir = Path("inputs/sft_processed")
    if processed_dir.exists():
        for version_dir in sorted(processed_dir.iterdir()):
            if version_dir.is_dir():
                train_json = version_dir / "train.json"
                if train_json.exists():
                    data = load_json(train_json)
                    task_dist = defaultdict(int)

                    for item in data:
                        task_type = detect_task_type_from_sft(item)
                        task_dist[task_type] += 1

                    dataset_results.append({
                        'name': f"sft_processed/{version_dir.name}",
                        'total': len(data),
                        'task_dist': dict(task_dist)
                    })

    return dataset_results, dict(all_task_dist)


def main():
    """メイン処理"""
    import sys

    output_file = "outputs/v3_final_analysis.txt"
    with open(output_file, 'w', encoding='utf-8') as f:
        old_stdout = sys.stdout
        sys.stdout = f

        # テストデータ読み込み
        test_data = load_json("test_data/public_150.json")

        # テストデータのタスク分布
        test_task_dist = defaultdict(int)
        for item in test_data:
            test_task_dist[item.get('task_name', 'Unknown')] += 1

        print("=" * 70)
        print("v3戦略最終分析レポート")
        print("=" * 70)

        # テストデータの分布
        print("\n" + "=" * 70)
        print("1. テストデータのタスク分布")
        print("=" * 70)

        for task, count in sorted(
            test_task_dist.items(), key=lambda x: -x[1]
        ):
            pct = count / len(test_data) * 100
            print(f"  {task}: {count} ({pct:.1f}%)")

        # SFTデータの分析
        print("\n" + "=" * 70)
        print("2. SFTデータセットのタスク分布（改善版検出）")
        print("=" * 70)

        dataset_results, all_sft_dist = analyze_sft_with_improved_detection()

        for ds in dataset_results:
            print(f"\n■ {ds['name']} ({ds['total']} 件)")
            for task, count in sorted(
                ds['task_dist'].items(), key=lambda x: -x[1]
            )[:10]:
                print(f"    {task}: {count}")

        # 全体の分布
        print("\n" + "-" * 70)
        print("■ SFT全体のタスク分布:")
        print("-" * 70)
        total_sft = sum(all_sft_dist.values())
        for task, count in sorted(all_sft_dist.items(), key=lambda x: -x[1]):
            pct = count / total_sft * 100
            print(f"  {task}: {count} ({pct:.1f}%)")

        # カバレッジ分析
        print("\n" + "=" * 70)
        print("3. テストデータ vs SFTデータ カバレッジ分析")
        print("=" * 70)

        print("\n■ テストデータの各タスクに対するSFTデータのカバレッジ:")
        print("-" * 70)

        coverage_issues = []
        for task, test_count in sorted(
            test_task_dist.items(), key=lambda x: -x[1]
        ):
            sft_count = all_sft_dist.get(task, 0)
            ratio = sft_count / test_count if test_count > 0 else 0
            status = "✓ 十分" if ratio >= 50 else "✗ 不足"
            print(f"  {task}:")
            print(f"    テスト: {test_count}, SFT: {sft_count}, "
                  f"比率: {ratio:.1f}, {status}")

            if ratio < 50:
                coverage_issues.append({
                    'task': task,
                    'test_count': test_count,
                    'sft_count': sft_count,
                    'ratio': ratio,
                    'target': test_count * 50,
                    'needed': max(0, test_count * 50 - sft_count)
                })

        # v3戦略の提案
        print("\n" + "=" * 70)
        print("4. v3戦略: 具体的なアクションプラン")
        print("=" * 70)

        print("\n【優先度1: 緊急にデータを追加すべきタスク】")
        print("（テストデータに存在するがSFTデータが全くない、または極端に少ない）")
        print("-" * 70)

        priority1 = [c for c in coverage_issues if c['ratio'] < 10]
        for item in sorted(priority1, key=lambda x: -x['test_count']):
            print(f"\n  ★ {item['task']}")
            print(f"    - テストデータ: {item['test_count']} 件")
            print(f"    - 現在のSFTデータ: {item['sft_count']} 件")
            print(f"    - 推奨追加数: {int(item['needed'])} 件以上")

        print("\n【優先度2: データを増やすべきタスク】")
        print("（SFTデータはあるが不足している）")
        print("-" * 70)

        priority2 = [c for c in coverage_issues if 10 <= c['ratio'] < 50]
        for item in sorted(priority2, key=lambda x: -x['test_count']):
            print(f"\n  ○ {item['task']}")
            print(f"    - テストデータ: {item['test_count']} 件")
            print(f"    - 現在のSFTデータ: {item['sft_count']} 件")
            print(f"    - 現在の比率: {item['ratio']:.1f}")
            print(f"    - 推奨追加数: {int(item['needed'])} 件")

        print("\n【データ品質改善】")
        print("-" * 70)
        print("  1. 出力にコードブロック(```)を含むデータの修正")
        print("  2. 説明テキスト(Here's, Let me)を含むデータの除去")
        print("  3. 思考プロセス(Approach:...)を含むデータは維持しつつ、")
        print("     最終出力が純粋なフォーマットになるよう確認")

        print("\n【推奨データソース/生成方法】")
        print("-" * 70)
        print("  1. 既存のテストデータを参考に類似パターンを生成")
        print("  2. 複雑なネスト構造（3-4階層）を含むデータを追加")
        print("  3. 配列、特殊文字、エスケープ処理を含むデータを追加")

        print("\n" + "=" * 70)
        print("分析完了")
        print("=" * 70)

        sys.stdout = old_stdout

    print(f"最終分析結果を {output_file} に保存しました")


if __name__ == "__main__":
    main()
