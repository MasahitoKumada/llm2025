#!/usr/bin/env python3
"""
v3戦略分析スクリプト

テストデータ（public_150.json）と各バージョンの推論結果を分析し、
データを増やす/減らす戦略を検討する。

スコア:
- v0: 0.69426
- v1: 0.59555（過学習で悪化）
- v2: 0.75074（最高スコア）
"""
import json
from collections import Counter, defaultdict


def load_json(path: str):
    """JSONファイルを読込む"""
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def analyze_test_data(test_data: list) -> dict:
    """テストデータの構造を分析"""
    task_names = Counter()
    output_types = Counter()
    rendering_count = Counter()

    for item in test_data:
        task_names[item.get('task_name', 'unknown')] += 1
        output_types[item.get('output_type', 'unknown')] += 1
        rendering_count[item.get('rendering', False)] += 1

    return {
        'total': len(test_data),
        'task_names': task_names,
        'output_types': output_types,
        'rendering_count': rendering_count
    }


def analyze_sft_data(sft_data: list) -> dict:
    """SFTデータの構造を分析"""
    formats = Counter()
    types = Counter()
    complexities = Counter()

    for item in sft_data:
        meta = item.get('metadata', {})
        formats[meta.get('format', 'unknown')] += 1
        types[meta.get('type', 'unknown')] += 1
        complexities[meta.get('complexity', 'unknown')] += 1

    return {
        'total': len(sft_data),
        'formats': formats,
        'types': types,
        'complexities': complexities
    }


def compare_inference_results(test_data: list, v0_data: list, v1_data: list, v2_data: list) -> dict:
    """推論結果を比較分析"""
    # task_idでインデックス化
    test_by_id = {item['task_id']: item for item in test_data}
    v0_by_id = {item['task_id']: item for item in v0_data}
    v1_by_id = {item['task_id']: item for item in v1_data}
    v2_by_id = {item['task_id']: item for item in v2_data}

    # 各タスク名ごとの結果を集計
    results_by_task = defaultdict(lambda: {'v0': [], 'v1': [], 'v2': []})

    for task_id, test_item in test_by_id.items():
        task_name = test_item.get('task_name', 'unknown')

        # 推論結果の長さを確認（空や短すぎる応答は問題の可能性）
        v0_output = v0_by_id.get(task_id, {}).get('output', '')
        v1_output = v1_by_id.get(task_id, {}).get('output', '')
        v2_output = v2_by_id.get(task_id, {}).get('output', '')

        results_by_task[task_name]['v0'].append(len(v0_output) if v0_output else 0)
        results_by_task[task_name]['v1'].append(len(v1_output) if v1_output else 0)
        results_by_task[task_name]['v2'].append(len(v2_output) if v2_output else 0)

    return results_by_task


def identify_coverage_gaps(test_analysis: dict, sft_analysis: dict) -> dict:
    """テストデータとSFTデータのカバレッジギャップを特定"""
    # テストデータのタスク名からSFTデータで必要なタイプを推定
    task_to_sft_mapping = {
        # Text to X → generation, format=X
        "Text to JSON": ("generation", "json"),
        "Text to YAML": ("generation", "yaml"),
        "Text to XML": ("generation", "xml"),
        "Text to TOML": ("generation", "toml"),
        "Text to CSV": ("generation", "csv"),
        # X to JSON → conversion (出力形式はjson)
        "CSV to JSON": ("conversion", "json"),
        "JSON to YAML": ("conversion", "yaml"),
        "XML to JSON": ("conversion", "json"),
        "YAML to JSON": ("conversion", "json"),
        "TOML to JSON": ("conversion", "json"),
        "TOML to YAML": ("conversion", "yaml"),
        "CSV to YAML": ("conversion", "yaml"),
        "XML to YAML": ("conversion", "yaml"),
        # X to XML/CSV などの変換
        "JSON to XML": ("conversion", "xml"),
        "YAML to XML": ("conversion", "xml"),
        "XML to CSV": ("conversion", "csv"),
        "YAML to CSV": ("conversion", "csv"),
        "JSON to CSV": ("conversion", "csv"),
        "CSV to XML": ("conversion", "xml"),
    }

    gaps = {}
    for task_name, count in test_analysis['task_names'].items():
        if task_name in task_to_sft_mapping:
            sft_type, sft_format = task_to_sft_mapping[task_name]
            sft_count = sft_analysis['formats'].get(sft_format, 0)
            gaps[task_name] = {
                'test_count': count,
                'sft_type': sft_type,
                'sft_format': sft_format,
                'sft_format_count': sft_count
            }

    return gaps


def main():
    print("=" * 80)
    print("v3戦略分析: テストデータとSFTデータのギャップ分析")
    print("=" * 80)
    print()
    print("スコア推移:")
    print("  v0: 0.69426")
    print("  v1: 0.59555 (過学習)")
    print("  v2: 0.75074 (最高)")
    print()

    # データ読み込み
    test_data = load_json('test_data/public_150.json')
    v0_data = load_json('outputs/inference_v0.json')
    v1_data = load_json('outputs/inference_v1.json')
    v2_data = load_json('outputs/inference_v2.json')

    # SFTデータセット読み込み（v2で使用したもの）
    sft_data = load_json('inputs/sft/1-1_512_v2/train.json')

    # テストデータ分析
    print("-" * 80)
    print("1. テストデータ分析 (public_150.json)")
    print("-" * 80)
    test_analysis = analyze_test_data(test_data)
    print(f"  総数: {test_analysis['total']}件")
    print()
    print("  タスク名分布:")
    for task, count in test_analysis['task_names'].most_common():
        pct = count / test_analysis['total'] * 100
        print(f"    {task}: {count}件 ({pct:.1f}%)")

    print()
    print("  出力形式分布:")
    for output_type, count in test_analysis['output_types'].most_common():
        pct = count / test_analysis['total'] * 100
        print(f"    {output_type}: {count}件 ({pct:.1f}%)")

    print()
    print("  レンダリング分布:")
    for rendering, count in test_analysis['rendering_count'].most_common():
        pct = count / test_analysis['total'] * 100
        print(f"    {rendering}: {count}件 ({pct:.1f}%)")

    # SFTデータ分析
    print()
    print("-" * 80)
    print("2. SFTデータ分析 (1-1_512_v2/train.json)")
    print("-" * 80)
    sft_analysis = analyze_sft_data(sft_data)
    print(f"  総数: {sft_analysis['total']}件")
    print()
    print("  フォーマット分布:")
    for fmt, count in sft_analysis['formats'].most_common():
        pct = count / sft_analysis['total'] * 100
        print(f"    {fmt}: {count}件 ({pct:.1f}%)")

    print()
    print("  タイプ分布:")
    for t, count in sft_analysis['types'].most_common():
        pct = count / sft_analysis['total'] * 100
        print(f"    {t}: {count}件 ({pct:.1f}%)")

    print()
    print("  複雑さ分布:")
    for comp, count in sft_analysis['complexities'].most_common():
        pct = count / sft_analysis['total'] * 100
        print(f"    {comp}: {count}件 ({pct:.1f}%)")

    # カバレッジギャップ分析
    print()
    print("-" * 80)
    print("3. カバレッジギャップ分析")
    print("-" * 80)
    gaps = identify_coverage_gaps(test_analysis, sft_analysis)

    print("  テストタスク → SFTデータ対応:")
    print()

    # タスクタイプ別に整理
    generation_tasks = []
    conversion_tasks = []

    for task_name, info in sorted(gaps.items()):
        if info['sft_type'] == 'generation':
            generation_tasks.append((task_name, info))
        else:
            conversion_tasks.append((task_name, info))

    print("  【Generation タスク（テキスト→構造化データ）】")
    for task_name, info in generation_tasks:
        coverage_ratio = info['sft_format_count'] / sft_analysis['total'] * 100
        print(f"    {task_name}: テスト{info['test_count']}件")
        print(f"      → SFT format={info['sft_format']}: {info['sft_format_count']}件 ({coverage_ratio:.1f}%)")

    print()
    print("  【Conversion タスク（形式変換）】")
    for task_name, info in conversion_tasks:
        coverage_ratio = info['sft_format_count'] / sft_analysis['total'] * 100
        print(f"    {task_name}: テスト{info['test_count']}件")
        print(f"      → SFT format={info['sft_format']}: {info['sft_format_count']}件 ({coverage_ratio:.1f}%)")

    # 推論結果比較
    print()
    print("-" * 80)
    print("4. 推論結果比較（出力長の傾向）")
    print("-" * 80)
    results_by_task = compare_inference_results(test_data, v0_data, v1_data, v2_data)

    for task_name in sorted(results_by_task.keys()):
        results = results_by_task[task_name]
        v0_avg = sum(results['v0']) / len(results['v0']) if results['v0'] else 0
        v1_avg = sum(results['v1']) / len(results['v1']) if results['v1'] else 0
        v2_avg = sum(results['v2']) / len(results['v2']) if results['v2'] else 0

        print(f"  {task_name} (n={len(results['v0'])})")
        print(f"    v0平均出力長: {v0_avg:.0f}文字")
        print(f"    v1平均出力長: {v1_avg:.0f}文字")
        print(f"    v2平均出力長: {v2_avg:.0f}文字")
        print()

    # 戦略提案
    print()
    print("=" * 80)
    print("5. v3データ戦略提案")
    print("=" * 80)
    print()

    # テストデータの分布を確認
    test_generation_count = sum(1 for item in test_data if item.get('task_name', '').startswith('Text to'))
    test_conversion_count = test_analysis['total'] - test_generation_count

    print("  テストデータの傾向:")
    print("    Generation (Text to X): {test_generation_count}件 ({test_generation_count/test_analysis['total']*100:.1f}%)")
    print("    Conversion (X to Y): {test_conversion_count}件 ({test_conversion_count/test_analysis['total']*100:.1f}%)")
    print()

    sft_generation_count = sft_analysis['types'].get('generation', 0)
    sft_conversion_count = sft_analysis['types'].get('conversion', 0)

    print("  SFTデータの傾向:")
    print("    Generation: {sft_generation_count}件 ({sft_generation_count/sft_analysis['total']*100:.1f}%)")
    print("    Conversion: {sft_conversion_count}件 ({sft_conversion_count/sft_analysis['total']*100:.1f}%)")
    print()

    print("  【提案】")
    print()

    # ギャップに基づく提案
    if test_conversion_count / test_analysis['total'] > sft_conversion_count / sft_analysis['total']:
        print("  ✓ Conversionデータを増やす:")
        print(f"    - テストでは{test_conversion_count/test_analysis['total']*100:.1f}%がConversionタスク")
        print(f"    - SFTでは{sft_conversion_count/sft_analysis['total']*100:.1f}%のみ")
        print("    → Conversionデータを追加することでカバレッジ改善")

    print()
    print("  ✓ フォーマット別のバランス調整:")

    # テストの出力形式分布とSFTのフォーマット分布を比較
    for output_type, test_count in test_analysis['output_types'].most_common():
        test_pct = test_count / test_analysis['total'] * 100
        sft_count = sft_analysis['formats'].get(output_type.lower(), 0)
        sft_pct = sft_count / sft_analysis['total'] * 100
        diff = test_pct - sft_pct

        if abs(diff) > 5:  # 5%以上の差があれば報告
            if diff > 0:
                print(f"    - {output_type}: テスト{test_pct:.1f}% vs SFT{sft_pct:.1f}% → データを増やす")
            else:
                print(f"    - {output_type}: テスト{test_pct:.1f}% vs SFT{sft_pct:.1f}% → 削減可能")

    print()
    print("  ✓ v2で成功した要因の維持:")
    print("    - v2はv0より+5.6%改善 → 学習設定が適切だった")
    print("    - データ量は3,933件で維持")
    print("    - 過度なデータ増加は避ける（v1の過学習の教訓）")

    print()
    print("  ✓ 具体的なアクション:")
    print("    1. 現在のデータを維持しつつ、Conversionタスクを強化")
    print("    2. テストで出現するタスクタイプを網羅するデータを追加")
    print("    3. XMLエラーなど品質問題のあるデータを除去")
    print("    4. Epoch数やLearning Rateの微調整も検討")


if __name__ == '__main__':
    main()
