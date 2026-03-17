#!/usr/bin/env python3
"""
v3 vs v2 推論結果の比較分析スクリプト

スコア:
- v0: 0.69426
- v1: 0.59555
- v2: 0.75074 (最高)
- v3: 0.72586 (v2より2.5ポイント低下)

v3がv2より低下した原因を分析する。
"""

import json
import re
from collections import defaultdict
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
TEST_DATA_PATH = BASE_DIR / "test_data" / "public_150.json"
OUTPUTS_DIR = BASE_DIR / "outputs"


def load_json(path):
    """JSONファイルを読込む"""
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def analyze_output_quality(generation, expected_format):
    """出力品質を分析"""
    issues = []
    # マークダウン囲みの検出
    if '```' in generation:
        issues.append('markdown_wrapped')
    # 説明文の検出
    explanation_patterns = [
        r"^Here's", r"^This (JSON|YAML|TOML|XML|CSV)",
        r"Notes:", r"^Below is", r"^I've",
        r"^The following", r"^Let me", r"✅",
        r"^This is", r"^Convert"
    ]
    for pattern in explanation_patterns:
        if re.search(pattern, generation, re.MULTILINE):
            issues.append('explanation_included')
            break
    # 空レスポンス
    if len(generation.strip()) < 10:
        issues.append('empty_response')
    # フォーマット検証
    if expected_format == 'JSON':
        clean = generation
        if '```json' in generation:
            match = re.search(
                r'```json\s*(.*?)\s*```', generation, re.DOTALL
            )
            if match:
                clean = match.group(1)
        elif '```' in generation:
            match = re.search(r'```\s*(.*?)\s*```', generation, re.DOTALL)
            if match:
                clean = match.group(1)
        try:
            json.loads(clean)
        except json.JSONDecodeError:
            issues.append('json_parse_error')

    return issues


def compare_versions(test_data, v2_data, v3_data):
    """v2とv3の比較"""
    test_map = {item['task_id']: item for item in test_data}
    v2_map = {item['task_id']: item for item in v2_data}
    v3_map = {item['task_id']: item for item in v3_data}

    comparison = {
        'total_tasks': len(test_data),
        'v2_issues': defaultdict(list),
        'v3_issues': defaultdict(list),
        'v2_only_issues': [],
        'v3_only_issues': [],
        'both_issues': [],
        'regression_by_task': defaultdict(list),
        'improvement_by_task': defaultdict(list),
    }

    for task_id, test_item in test_map.items():
        task_name = test_item.get('task_name', 'unknown')
        expected_format = test_item.get('output_type', 'JSON')

        v2_gen = v2_map.get(task_id, {}).get('generation', '')
        v3_gen = v3_map.get(task_id, {}).get('generation', '')

        v2_issues = analyze_output_quality(v2_gen, expected_format)
        v3_issues = analyze_output_quality(v3_gen, expected_format)

        for issue in v2_issues:
            comparison['v2_issues'][issue].append(task_id)
        for issue in v3_issues:
            comparison['v3_issues'][issue].append(task_id)

        # v3で新たに発生した問題
        new_issues = set(v3_issues) - set(v2_issues)
        if new_issues:
            comparison['v2_only_issues'].append({
                'task_id': task_id,
                'task_name': task_name,
                'new_issues': list(new_issues)
            })
            for issue in new_issues:
                comparison['regression_by_task'][task_name].append({
                    'task_id': task_id,
                    'issue': issue
                })

        # v3で解消した問題
        fixed_issues = set(v2_issues) - set(v3_issues)
        if fixed_issues:
            comparison['v3_only_issues'].append({
                'task_id': task_id,
                'task_name': task_name,
                'fixed_issues': list(fixed_issues)
            })
            for issue in fixed_issues:
                comparison['improvement_by_task'][task_name].append({
                    'task_id': task_id,
                    'issue': issue
                })

    return comparison


def analyze_output_length_diff(v2_data, v3_data):
    """出力長の差異を分析"""
    v2_map = {item['task_id']: item for item in v2_data}
    v3_map = {item['task_id']: item for item in v3_data}

    length_diffs = []
    for task_id in v2_map:
        v2_len = len(v2_map[task_id].get('generation', ''))
        v3_gen = v3_map.get(task_id, {}).get('generation', '')
        v3_len = len(v3_gen) if v3_gen else 0

        diff = v3_len - v2_len
        length_diffs.append({
            'task_id': task_id,
            'v2_len': v2_len,
            'v3_len': v3_len,
            'diff': diff,
            'ratio': v3_len / v2_len if v2_len > 0 else 0
        })

    return sorted(length_diffs, key=lambda x: x['diff'])


def sample_outputs(test_data, v2_data, v3_data, task_ids, max_samples=3):
    """特定タスクの出力サンプルを取得"""
    test_map = {item['task_id']: item for item in test_data}
    v2_map = {item['task_id']: item for item in v2_data}
    v3_map = {item['task_id']: item for item in v3_data}

    samples = []
    for task_id in task_ids[:max_samples]:
        test_item = test_map.get(task_id, {})
        samples.append({
            'task_id': task_id,
            'task_name': test_item.get('task_name', 'unknown'),
            'query_preview': test_item.get('query', '')[:200] + '...',
            'v2_output': v2_map.get(task_id, {}).get('generation', '')[:500],
            'v3_output': v3_map.get(task_id, {}).get('generation', '')[:500],
        })
    return samples


def main():
    print("=" * 80)
    print("v3 vs v2 推論結果比較分析")
    print("=" * 80)
    print("\nスコア推移:")
    print("  v0: 0.69426")
    print("  v1: 0.59555")
    print("  v2: 0.75074 (最高)")
    print("  v3: 0.72586 (v2より2.5ポイント低下)")

    # データ読み込み
    test_data = load_json(TEST_DATA_PATH)
    v2_data = load_json(OUTPUTS_DIR / "inference_v2.json")
    v3_data = load_json(OUTPUTS_DIR / "inference_v3.json")

    # 比較分析
    comparison = compare_versions(test_data, v2_data, v3_data)

    print("\n" + "=" * 80)
    print("📊 品質問題の比較")
    print("=" * 80)

    print("\n【v2の品質問題】")
    for issue, tasks in comparison['v2_issues'].items():
        print(f"  {issue}: {len(tasks)}件")

    print("\n【v3の品質問題】")
    for issue, tasks in comparison['v3_issues'].items():
        print(f"  {issue}: {len(tasks)}件")

    print("\n" + "=" * 80)
    print("🔻 v3で悪化したタスク（リグレッション）")
    print("=" * 80)

    print(f"\nv3で新たに問題が発生: {len(comparison['v2_only_issues'])}件")

    # タスクタイプ別の悪化
    print("\n【タスクタイプ別リグレッション】")
    for task_name, regressions in sorted(
        comparison['regression_by_task'].items(),
        key=lambda x: -len(x[1])
    ):
        print(f"  {task_name}: {len(regressions)}件")
        for reg in regressions[:2]:
            print(f"    - {reg['task_id']}: {reg['issue']}")

    print("\n" + "=" * 80)
    print("🔺 v3で改善したタスク")
    print("=" * 80)

    print(f"\nv3で問題が解消: {len(comparison['v3_only_issues'])}件")

    # タスクタイプ別の改善
    print("\n【タスクタイプ別改善】")
    for task_name, improvements in sorted(
        comparison['improvement_by_task'].items(),
        key=lambda x: -len(x[1])
    ):
        print(f"  {task_name}: {len(improvements)}件")

    # 出力長の差異
    print("\n" + "=" * 80)
    print("📏 出力長の差異分析")
    print("=" * 80)

    length_diffs = analyze_output_length_diff(v2_data, v3_data)

    # 統計
    avg_v2 = sum(d['v2_len'] for d in length_diffs) / len(length_diffs)
    avg_v3 = sum(d['v3_len'] for d in length_diffs) / len(length_diffs)
    avg_diff = sum(d['diff'] for d in length_diffs) / len(length_diffs)

    print("\n平均出力長:")
    print(f"  v2: {avg_v2:.0f}文字")
    print(f"  v3: {avg_v3:.0f}文字")
    print(f"  差分: {avg_diff:+.0f}文字 ({avg_diff/avg_v2*100:+.1f}%)")

    # 極端に短くなったケース
    short_cases = [
        d for d in length_diffs
        if d['ratio'] < 0.5 and d['v2_len'] > 100
    ]
    if short_cases:
        print(f"\n⚠️ 極端に短くなったケース（50%未満）: {len(short_cases)}件")
        for case in short_cases[:5]:
            print(f"  {case['task_id']}: {case['v2_len']} → {case['v3_len']}")

    # 極端に長くなったケース
    long_cases = [
        d for d in length_diffs
        if d['ratio'] > 2.0 and d['v2_len'] > 100
    ]
    if long_cases:
        print(f"\n⚠️ 極端に長くなったケース（200%超）: {len(long_cases)}件")
        for case in long_cases[:5]:
            print(f"  {case['task_id']}: {case['v2_len']} → {case['v3_len']}")

    # 悪化したタスクのサンプル
    if comparison['v2_only_issues']:
        print("\n" + "=" * 80)
        print("📝 悪化したタスクのサンプル出力")
        print("=" * 80)

        regression_ids = [
            r['task_id'] for r in comparison['v2_only_issues'][:3]
        ]
        samples = sample_outputs(test_data, v2_data, v3_data, regression_ids)

        for sample in samples:
            print(f"\n--- {sample['task_id']} ({sample['task_name']}) ---")
            print(f"Query: {sample['query_preview']}")
            print(f"\nv2出力:\n{sample['v2_output']}")
            print(f"\nv3出力:\n{sample['v3_output']}")

    # 分析結果の保存
    v2_issues_count = {k: len(v) for k, v in comparison['v2_issues'].items()}
    v3_issues_count = {k: len(v) for k, v in comparison['v3_issues'].items()}
    result = {
        'scores': {
            'v0': 0.69426,
            'v1': 0.59555,
            'v2': 0.75074,
            'v3': 0.72586
        },
        'v2_issues_count': v2_issues_count,
        'v3_issues_count': v3_issues_count,
        'regression_count': len(comparison['v2_only_issues']),
        'improvement_count': len(comparison['v3_only_issues']),
        'regression_by_task': {
            k: len(v) for k, v in comparison['regression_by_task'].items()
        },
        'avg_output_length': {
            'v2': avg_v2,
            'v3': avg_v3,
            'diff': avg_diff
        }
    }

    output_path = BASE_DIR / "docs" / "v3_vs_v2_analysis.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 分析結果を {output_path} に保存しました")

    # 原因と対策の推定
    print("\n" + "=" * 80)
    print("💡 v3低下の原因推定と対策")
    print("=" * 80)

    print("\n【原因推定】")
    print("1. データセット構成の変更による過学習または一般化性能の低下")
    print("2. 特定タスクタイプへの過度な最適化による他タスクの精度低下")
    print("3. データ品質フィルタリングで有用なサンプルも除外された可能性")

    print("\n【v4への対策案】")
    print("1. v2のデータセット構成をベースに、最小限の調整のみ行う")
    print("2. リグレッションが多いタスクタイプのデータを重点的に追加")
    print("3. データ増減は慎重に、A/Bテスト的なアプローチで検証")


if __name__ == "__main__":
    main()
