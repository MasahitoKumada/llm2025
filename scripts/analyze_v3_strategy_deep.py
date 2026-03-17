#!/usr/bin/env python3
"""
v3戦略深層分析スクリプト

スコア推移:
- 1回目 (v0): 0.69426
- 2回目 (v1): 0.59555 (悪化)
- 3回目 (v2): 0.75074 (最高)

テストデータと推論結果、SFTデータセットを分析し、
データ増減戦略を検討する。
"""

import json
from collections import Counter, defaultdict
from pathlib import Path


def load_json(path: str) -> list:
    """JSONファイルを読込む"""
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def analyze_test_data(test_data: list) -> dict:
    """テストデータの特性を分析"""
    print("=" * 70)
    print("テストデータ分析 (public_150.json)")
    print("=" * 70)

    task_names = Counter()
    for item in test_data:
        task_names[item.get('task_name', 'unknown')] += 1

    print(f"\n総件数: {len(test_data)}")
    print("\nタスク名分布:")
    for task, count in task_names.most_common():
        pct = count / len(test_data) * 100
        print(f"  {task}: {count}件 ({pct:.1f}%)")

    # タスクタイプを分類
    generation_tasks = [k for k in task_names if k.startswith("Text to")]
    conversion_tasks = [
        k for k in task_names
        if " to " in k and not k.startswith("Text to")
    ]

    gen_count = sum(task_names[t] for t in generation_tasks)
    conv_count = sum(task_names[t] for t in conversion_tasks)

    print("\nタスクタイプ:")
    gen_pct = gen_count / len(test_data) * 100
    conv_pct = conv_count / len(test_data) * 100
    print(f"  Generation (Text to X): {gen_count}件 ({gen_pct:.1f}%)")
    print(f"  Conversion (X to Y): {conv_count}件 ({conv_pct:.1f}%)")

    # 出力フォーマット分析
    output_formats = Counter()
    for task, count in task_names.items():
        if " to " in task:
            output_format = task.split(" to ")[-1].lower()
            output_formats[output_format] += count

    print("\n出力フォーマット分布:")
    for fmt, count in output_formats.most_common():
        pct = count / len(test_data) * 100
        print(f"  {fmt}: {count}件 ({pct:.1f}%)")

    return {
        'task_names': dict(task_names),
        'generation_count': gen_count,
        'conversion_count': conv_count,
        'output_formats': dict(output_formats)
    }


def analyze_inference_results(
    inference_data: list,
    version: str,
    test_data: list
) -> dict:
    """推論結果を分析"""
    print(f"\n{'=' * 70}")
    print(f"推論結果分析: {version}")
    print("=" * 70)

    # テストデータと推論結果を対応付け
    task_results = defaultdict(list)
    test_by_id = {item['task_id']: item for item in test_data}

    for inference_item in inference_data:
        task_id = inference_item.get('task_id', '')
        test_item = test_by_id.get(task_id, {})
        task_name = test_item.get('task_name', 'unknown')
        output = inference_item.get('generation', '')

        # 出力の品質を簡易評価
        has_content = len(output.strip()) > 0
        has_code_fence = '```' in output
        explanation_phrases = [
            'here is', "here's", 'the following', 'below is'
        ]
        has_explanation = any(
            phrase in output.lower() for phrase in explanation_phrases
        )

        task_results[task_name].append({
            'has_content': has_content,
            'has_code_fence': has_code_fence,
            'has_explanation': has_explanation,
            'output_length': len(output)
        })

    print(f"\n総件数: {len(inference_data)}")

    # タスクごとの品質サマリー
    print("\nタスクごとの出力品質:")
    for task_name, results in sorted(task_results.items()):
        total = len(results)
        with_content = sum(1 for r in results if r['has_content'])
        with_fence = sum(1 for r in results if r['has_code_fence'])
        with_explain = sum(1 for r in results if r['has_explanation'])
        if total > 0:
            avg_len = sum(r['output_length'] for r in results) / total
        else:
            avg_len = 0

        content_pct = with_content / total * 100 if total > 0 else 0
        fence_pct = with_fence / total * 100 if total > 0 else 0
        explain_pct = with_explain / total * 100 if total > 0 else 0

        print(f"\n  {task_name} ({total}件):")
        print(f"    - 内容あり: {with_content}/{total} ({content_pct:.0f}%)")
        print(f"    - コードフェンス: {with_fence}/{total} ({fence_pct:.0f}%)")
        print(f"    - 前置き文: {with_explain}/{total} ({explain_pct:.0f}%)")
        print(f"    - 平均長: {avg_len:.0f}文字")

    return dict(task_results)


def analyze_sft_datasets():
    """SFTデータセットを分析"""
    print(f"\n{'=' * 70}")
    print("SFTデータセット分析")
    print("=" * 70)

    sft_dir = Path("inputs/sft")
    datasets = {}

    for dataset_dir in sorted(sft_dir.iterdir()):
        if not dataset_dir.is_dir():
            continue

        train_json = dataset_dir / "train.json"
        if not train_json.exists():
            continue

        data = load_json(str(train_json))
        datasets[dataset_dir.name] = data

        print(f"\n--- {dataset_dir.name} ({len(data)}件) ---")

        # メタデータ分析（あれば）
        if data and 'metadata' in data[0]:
            format_counts = Counter()
            type_counts = Counter()

            for item in data:
                meta = item.get('metadata', {})
                format_counts[meta.get('format', 'unknown')] += 1
                type_counts[meta.get('type', 'unknown')] += 1

            print("  フォーマット分布:")
            for fmt, count in format_counts.most_common():
                pct = count / len(data) * 100
                print(f"    {fmt}: {count}件 ({pct:.1f}%)")

            print("  タイプ分布:")
            for t, count in type_counts.most_common():
                pct = count / len(data) * 100
                print(f"    {t}: {count}件 ({pct:.1f}%)")
        else:
            # conversationsを分析
            print("  会話データ形式")
            sample = data[0] if data else {}
            print(f"  キー: {list(sample.keys())}")

    return datasets


def analyze_output_errors(
    inference_data: list,
    test_data: list,
    version: str
):
    """出力エラーの詳細分析"""
    print(f"\n{'=' * 70}")
    print(f"出力エラー詳細分析: {version}")
    print("=" * 70)

    error_categories = {
        'code_fence': [],
        'explanation': [],
        'empty': [],
        'very_short': [],
        'very_long': [],
    }

    test_by_id = {item['task_id']: item for item in test_data}

    for inference_item in inference_data:
        task_id = inference_item.get('task_id', '')
        test_item = test_by_id.get(task_id, {})
        task_name = test_item.get('task_name', 'unknown')
        output = inference_item.get('generation', '')

        if len(output.strip()) == 0:
            error_categories['empty'].append((task_id, task_name))
        elif len(output) < 10:
            error_categories['very_short'].append((task_id, task_name))
        elif len(output) > 2000:
            error_categories['very_long'].append((task_id, task_name))

        if '```' in output:
            error_categories['code_fence'].append((task_id, task_name))

        explanation_phrases = [
            'here is', "here's", 'the following', 'below is', 'i will'
        ]
        if any(phrase in output.lower() for phrase in explanation_phrases):
            error_categories['explanation'].append((task_id, task_name))

    for category, errors in error_categories.items():
        print(f"\n{category}: {len(errors)}件")
        if errors:
            task_counts = Counter(e[1] for e in errors)
            print("  タスク内訳:")
            for task, count in task_counts.most_common():
                print(f"    {task}: {count}件")


def compare_versions(
    v0_results: list,
    v1_results: list,
    v2_results: list,
    test_data: list
):
    """バージョン間の比較"""
    print(f"\n{'=' * 70}")
    print("バージョン間比較")
    print("=" * 70)

    versions = {
        'v0 (0.69426)': v0_results,
        'v1 (0.59555)': v1_results,
        'v2 (0.75074)': v2_results,
    }

    # task_idでインデックス化
    test_by_id = {item['task_id']: item for item in test_data}

    task_names_set = set()
    for item in test_data:
        task_names_set.add(item.get('task_name', 'unknown'))

    for task_name in sorted(task_names_set):
        print(f"\n{task_name}:")

        task_ids = [
            item['task_id'] for item in test_data
            if item.get('task_name') == task_name
        ]

        for ver_name, results in versions.items():
            result_by_id = {r['task_id']: r for r in results}

            fence_count = 0
            explain_count = 0
            total_len = 0

            for tid in task_ids:
                result = result_by_id.get(tid, {})
                output = result.get('generation', '')
                if '```' in output:
                    fence_count += 1
                exp_phrases = ['here is', "here's", 'the following']
                if any(p in output.lower() for p in exp_phrases):
                    explain_count += 1
                total_len += len(output)

            avg_len = total_len / len(task_ids) if task_ids else 0
            print(f"  {ver_name}: フェンス={fence_count}, "
                  f"説明文={explain_count}, 平均長={avg_len:.0f}")


def propose_data_strategy(test_analysis: dict, sft_datasets: dict):
    """データ増減戦略を提案"""
    print(f"\n{'=' * 70}")
    print("データ増減戦略提案")
    print("=" * 70)

    print("\n【現状の課題】")
    print("1. v0(0.69426)→v1(0.59555): 大幅悪化 - 何かが間違っている")
    print("2. v1(0.59555)→v2(0.75074): 改善 - 効果的な変更があった")
    print("3. テストはConversion(73%)が多いが、"
          "Generation用データが多い可能性")

    print("\n【Person Hの成功例から学ぶべき点】")
    print("- SFT単独で0.82達成（最高スコア）")
    print("- DPO単独で0.76")
    print("- SFT+DPOで0.73に悪化")

    print("\n【データ増やす戦略】")
    print("1. Conversionタスク（X to Y）のデータを増強")
    print("   - CSV to JSON/YAML/XML")
    print("   - YAML to XML")
    print("   - XML to JSON/YAML")
    print("2. 難しいフォーマット（TOML, XML）のデータを増強")

    print("\n【データ減らす戦略】")
    print("1. XMLデータのlintエラー除去（Person C: 64/1076=5.95%）")
    print("2. 余計な前置き文が出力されやすいデータの除去")
    print("3. 品質の低いデータの除去")

    print("\n【学習パラメータの戦略】")
    print("1. Epoch=2の採用（Person Eの成功例）")
    print("2. 過学習を避けるパラメータ調整")

    print("\n【推奨v3戦略】")
    print("Option A: v2データを基盤に品質向上")
    print("  - XMLのlintエラーデータ64件を除去")
    print("  - Epoch=2で学習")
    print("  - 余計な前置き文を出力しないようprompt工夫")

    print("\nOption B: DPOに転換")
    print("  - SFT済みモデルをベースにDPO")
    print("  - chosen/rejectedの長さ偏りを修正")
    print("  - XMLパースエラーデータの除外")


def main():
    """メイン処理"""
    # データ読み込み
    print("データ読み込み中...")
    test_data = load_json("test_data/public_150.json")
    v0_results = load_json("outputs/inference_v0.json")
    v1_results = load_json("outputs/inference_v1.json")
    v2_results = load_json("outputs/inference_v2.json")

    # テストデータ分析
    test_analysis = analyze_test_data(test_data)

    # 推論結果分析
    analyze_inference_results(v0_results, "v0 (score: 0.69426)", test_data)
    analyze_inference_results(v1_results, "v1 (score: 0.59555)", test_data)
    analyze_inference_results(v2_results, "v2 (score: 0.75074)", test_data)

    # 出力エラー分析
    analyze_output_errors(v0_results, test_data, "v0")
    analyze_output_errors(v1_results, test_data, "v1")
    analyze_output_errors(v2_results, test_data, "v2")

    # SFTデータセット分析
    sft_datasets = analyze_sft_datasets()

    # バージョン間比較
    compare_versions(v0_results, v1_results, v2_results, test_data)

    # 戦略提案
    propose_data_strategy(test_analysis, sft_datasets)


if __name__ == "__main__":
    main()
