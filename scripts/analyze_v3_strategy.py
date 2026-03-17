#!/usr/bin/env python3
"""
v3戦略分析スクリプト

テストデータ（public_150.json）、SFTデータセット、推論結果を分析し、
データ増減の戦略を提案する。

スコア:
- v0: 0.69426
- v1: 0.59555
- v2: 0.75074
"""

import json
import os
import re
from pathlib import Path
from collections import Counter, defaultdict
from typing import Dict, List, Tuple, Optional
import yaml
import toml
import xml.etree.ElementTree as ET
import pandas as pd
import io

# パス設定
BASE_DIR = Path(__file__).parent.parent
TEST_DATA_PATH = BASE_DIR / "test_data" / "public_150.json"
SFT_DIR = BASE_DIR / "inputs" / "sft"
OUTPUT_DIR = BASE_DIR / "outputs"


def count_tokens(text: str) -> int:
    """簡易トークン数カウント（文字数/4で近似）"""
    return len(text) // 4 if text else 0


def extract_content(text: str) -> Tuple[str, str]:
    """コードフェンスを除去してコンテンツを抽出"""
    text = text.strip()
    fence_pattern = r'```(?:\w+)?\s*\n?(.*?)```'
    fence_match = re.search(fence_pattern, text, re.DOTALL | re.IGNORECASE)
    if fence_match:
        return fence_match.group(1).strip(), "fence"
    return text, "raw"


def validate_format(text: str, output_type: str) -> Tuple[bool, str]:
    """出力フォーマットの検証"""
    content, _ = extract_content(text)
    output_type = output_type.upper()

    try:
        if output_type == 'JSON':
            json.loads(content)
        elif output_type == 'YAML':
            yaml.safe_load(content)
        elif output_type == 'TOML':
            toml.loads(content)
        elif output_type == 'XML':
            ET.fromstring(content)
        elif output_type == 'CSV':
            if not content.strip():
                raise ValueError("Empty CSV")
            pd.read_csv(io.StringIO(content))
        else:
            return False, f"Unknown format: {output_type}"
        return True, ""
    except Exception as e:
        return False, str(e)


def load_test_data() -> List[Dict]:
    """テストデータを読み込み"""
    with open(TEST_DATA_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_inference_data(version: str) -> Dict[str, str]:
    """推論結果を読み込み"""
    path = OUTPUT_DIR / f"inference_{version}.json"
    if not path.exists():
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return {item['task_id']: item.get('generation', '') for item in data}


def load_sft_datasets() -> Dict[str, List[Dict]]:
    """全SFTデータセットを読み込み"""
    datasets = {}
    for subdir in SFT_DIR.iterdir():
        if subdir.is_dir():
            json_path = subdir / "train.json"
            if json_path.exists():
                with open(json_path, 'r', encoding='utf-8') as f:
                    datasets[subdir.name] = json.load(f)
    return datasets


def analyze_test_data(test_data: List[Dict]) -> Dict:
    """テストデータの分析"""
    print("\n" + "="*60)
    print("📊 テストデータ分析 (public_150.json)")
    print("="*60)

    task_names = Counter(item['task_name'] for item in test_data)
    output_types = Counter(item['output_type'] for item in test_data)
    query_tokens = [count_tokens(item['query']) for item in test_data]

    print(f"\n総件数: {len(test_data)}")

    print("\n### task_name 分布:")
    for name, count in task_names.most_common():
        pct = count / len(test_data) * 100
        print(f"  {name}: {count} ({pct:.1f}%)")

    print("\n### output_type 分布:")
    for otype, count in output_types.most_common():
        pct = count / len(test_data) * 100
        print(f"  {otype}: {count} ({pct:.1f}%)")

    print("\n### query トークン数統計:")
    print(f"  最小: {min(query_tokens)}")
    print(f"  最大: {max(query_tokens)}")
    print(f"  平均: {sum(query_tokens)/len(query_tokens):.1f}")

    # task_name × output_type のクロス集計
    cross_table = defaultdict(Counter)
    for item in test_data:
        cross_table[item['task_name']][item['output_type']] += 1

    print("\n### task_name × output_type クロス集計:")
    for task_name in sorted(cross_table.keys()):
        print(f"\n  {task_name}:")
        for otype, count in cross_table[task_name].most_common():
            print(f"    - {otype}: {count}")

    return {
        'task_names': task_names,
        'output_types': output_types,
        'query_tokens': query_tokens,
        'cross_table': cross_table,
    }


def analyze_sft_datasets(datasets: Dict[str, List[Dict]]) -> Dict:
    """SFTデータセットの分析"""
    print("\n" + "="*60)
    print("📚 SFTデータセット分析")
    print("="*60)

    all_formats = Counter()
    all_complexities = Counter()
    all_schemas = Counter()
    all_types = Counter()

    for name, data in sorted(datasets.items()):
        print(f"\n### {name} ({len(data)} 件)")

        formats = Counter()
        complexities = Counter()
        schemas = Counter()
        types = Counter()
        tokens = []

        for item in data:
            meta = item.get('metadata', {})
            fmt = meta.get('format', 'unknown')
            complexity = meta.get('complexity', 'unknown')
            schema = meta.get('schema', 'unknown')
            item_type = meta.get('type', 'unknown')
            est_tokens = meta.get('estimated_tokens', 0)

            formats[fmt] += 1
            complexities[complexity] += 1
            schemas[schema] += 1
            types[item_type] += 1
            tokens.append(est_tokens)

            all_formats[fmt] += 1
            all_complexities[complexity] += 1
            all_schemas[schema] += 1
            all_types[item_type] += 1

        print(f"  format分布: {dict(formats.most_common(5))}")
        print(f"  complexity分布: {dict(complexities)}")
        print(f"  type分布: {dict(types)}")
        if tokens:
            print(f"  tokens: min={min(tokens)}, max={max(tokens)}, avg={sum(tokens)/len(tokens):.0f}")

    print("\n### 全データセット合計:")
    print(f"  format: {dict(all_formats.most_common())}")
    print(f"  complexity: {dict(all_complexities)}")
    print(f"  type: {dict(all_types)}")

    return {
        'all_formats': all_formats,
        'all_complexities': all_complexities,
        'all_schemas': all_schemas,
        'all_types': all_types,
    }


def analyze_inference_results(
    test_data: List[Dict],
    inference_maps: Dict[str, Dict[str, str]]
) -> Dict:
    """推論結果の分析"""
    print("\n" + "="*60)
    print("🔍 推論結果分析")
    print("="*60)

    results = {}

    for version, inf_map in sorted(inference_maps.items()):
        print(f"\n### {version}")

        valid_count = 0
        invalid_count = 0
        by_task_name = defaultdict(lambda: {'valid': 0, 'invalid': 0})
        by_output_type = defaultdict(lambda: {'valid': 0, 'invalid': 0})
        invalid_examples = []

        for item in test_data:
            task_id = item['task_id']
            task_name = item['task_name']
            output_type = item['output_type']
            generation = inf_map.get(task_id, "")

            is_valid, error = validate_format(generation, output_type)

            if is_valid:
                valid_count += 1
                by_task_name[task_name]['valid'] += 1
                by_output_type[output_type]['valid'] += 1
            else:
                invalid_count += 1
                by_task_name[task_name]['invalid'] += 1
                by_output_type[output_type]['invalid'] += 1
                if len(invalid_examples) < 3:
                    invalid_examples.append({
                        'task_id': task_id,
                        'task_name': task_name,
                        'output_type': output_type,
                        'error': error[:100],
                    })

        total = valid_count + invalid_count
        accuracy = valid_count / total * 100 if total > 0 else 0

        print(f"  フォーマット正答率: {valid_count}/{total} ({accuracy:.1f}%)")

        print("\n  task_nameごとの正答率:")
        for name in sorted(by_task_name.keys()):
            stats = by_task_name[name]
            total_name = stats['valid'] + stats['invalid']
            acc = stats['valid'] / total_name * 100 if total_name > 0 else 0
            print(f"    {name}: {stats['valid']}/{total_name} ({acc:.1f}%)")

        print("\n  output_typeごとの正答率:")
        for otype in sorted(by_output_type.keys()):
            stats = by_output_type[otype]
            total_otype = stats['valid'] + stats['invalid']
            acc = stats['valid'] / total_otype * 100 if total_otype > 0 else 0
            print(f"    {otype}: {stats['valid']}/{total_otype} ({acc:.1f}%)")

        if invalid_examples:
            print("\n  エラー例:")
            for ex in invalid_examples:
                print(f"    - {ex['task_id'][:20]}... [{ex['task_name']}][{ex['output_type']}]")
                print(f"      Error: {ex['error']}")

        results[version] = {
            'valid': valid_count,
            'invalid': invalid_count,
            'accuracy': accuracy,
            'by_task_name': dict(by_task_name),
            'by_output_type': dict(by_output_type),
        }

    return results


def compare_versions(
    test_data: List[Dict],
    inference_maps: Dict[str, Dict[str, str]]
) -> None:
    """バージョン間の比較分析"""
    print("\n" + "="*60)
    print("📈 バージョン間比較")
    print("="*60)

    versions = sorted(inference_maps.keys())
    if len(versions) < 2:
        print("比較できるバージョンが不足しています")
        return

    # v0 vs v2 の詳細比較
    v0_map = inference_maps.get('v0', {})
    v2_map = inference_maps.get('v2', {})

    if not v0_map or not v2_map:
        return

    improved = []  # v0で失敗、v2で成功
    regressed = []  # v0で成功、v2で失敗
    both_success = []
    both_fail = []

    for item in test_data:
        task_id = item['task_id']
        output_type = item['output_type']

        v0_valid, _ = validate_format(v0_map.get(task_id, ""), output_type)
        v2_valid, _ = validate_format(v2_map.get(task_id, ""), output_type)

        if v0_valid and v2_valid:
            both_success.append(item)
        elif not v0_valid and v2_valid:
            improved.append(item)
        elif v0_valid and not v2_valid:
            regressed.append(item)
        else:
            both_fail.append(item)

    print(f"\n### v0 → v2 の変化:")
    print(f"  両方成功: {len(both_success)}")
    print(f"  改善（v0失敗→v2成功）: {len(improved)}")
    print(f"  劣化（v0成功→v2失敗）: {len(regressed)}")
    print(f"  両方失敗: {len(both_fail)}")

    if improved:
        print("\n  改善したタスク:")
        for item in improved[:5]:
            print(f"    - {item['task_name']} [{item['output_type']}]")

    if regressed:
        print("\n  劣化したタスク:")
        for item in regressed[:5]:
            print(f"    - {item['task_name']} [{item['output_type']}]")

    if both_fail:
        print("\n  両方失敗したタスク（重点改善候補）:")
        fail_by_task = Counter(item['task_name'] for item in both_fail)
        fail_by_type = Counter(item['output_type'] for item in both_fail)
        print(f"    task_name分布: {dict(fail_by_task)}")
        print(f"    output_type分布: {dict(fail_by_type)}")


def suggest_strategy(
    test_analysis: Dict,
    sft_analysis: Dict,
    inference_results: Dict
) -> None:
    """戦略提案"""
    print("\n" + "="*60)
    print("💡 v3戦略提案")
    print("="*60)

    # テストデータのoutput_type分布
    test_output_types = test_analysis['output_types']

    # SFTデータのformat分布
    sft_formats = sft_analysis['all_formats']

    print("\n### 1. データ分布の比較")
    print("\nテストデータ output_type vs SFTデータ format:")

    # 対応表を作成（output_typeとformatのマッピング）
    format_mapping = {
        'JSON': 'json',
        'YAML': 'yaml',
        'TOML': 'toml',
        'XML': 'xml',
        'CSV': 'csv',
    }

    total_test = sum(test_output_types.values())
    total_sft = sum(sft_formats.values())

    print(f"\n{'Format':<10} | {'テスト件数':<12} | {'テスト%':<8} | {'SFT件数':<12} | {'SFT%':<8} | 差分")
    print("-" * 70)

    for otype, sft_format in format_mapping.items():
        test_count = test_output_types.get(otype, 0)
        sft_count = sft_formats.get(sft_format, 0)
        test_pct = test_count / total_test * 100 if total_test > 0 else 0
        sft_pct = sft_count / total_sft * 100 if total_sft > 0 else 0
        diff = sft_pct - test_pct
        indicator = "⬆️" if diff > 5 else "⬇️" if diff < -5 else "≈"
        print(f"{otype:<10} | {test_count:<12} | {test_pct:<8.1f} | {sft_count:<12} | {sft_pct:<8.1f} | {diff:+.1f}% {indicator}")

    # v2の結果を分析
    if 'v2' in inference_results:
        v2_results = inference_results['v2']
        print("\n### 2. v2の弱点分析")

        # output_typeごとの精度
        weak_types = []
        for otype, stats in v2_results['by_output_type'].items():
            total = stats['valid'] + stats['invalid']
            acc = stats['valid'] / total * 100 if total > 0 else 0
            if acc < 80:
                weak_types.append((otype, acc, total))

        if weak_types:
            print("\n精度80%未満のoutput_type:")
            for otype, acc, total in sorted(weak_types, key=lambda x: x[1]):
                print(f"  - {otype}: {acc:.1f}% ({total}件)")

        # task_nameごとの精度
        weak_tasks = []
        for task_name, stats in v2_results['by_task_name'].items():
            total = stats['valid'] + stats['invalid']
            acc = stats['valid'] / total * 100 if total > 0 else 0
            if acc < 80:
                weak_tasks.append((task_name, acc, total))

        if weak_tasks:
            print("\n精度80%未満のtask_name:")
            for task_name, acc, total in sorted(weak_tasks, key=lambda x: x[1]):
                print(f"  - {task_name}: {acc:.1f}% ({total}件)")

    print("\n### 3. 具体的な戦略提案")

    print("""
【データを増やすべきカテゴリ】
1. テストデータに多いがSFTデータに少ないformat
2. 精度が低いtask_name/output_typeの組み合わせ
3. 複雑なネスト構造を持つデータ

【データを減らす/調整すべきカテゴリ】
1. テストデータに少ないがSFTデータに多すぎるformat
2. 過剰に簡単なデータ（精度100%のカテゴリ）
3. テストデータと無関係なschema

【その他の改善提案】
1. コードフェンス```の扱いを統一（v2では改善済み）
2. 出力フォーマットの厳密化（余計な説明を含まない）
3. エッジケース（空配列、null値、特殊文字）のデータ追加
""")


def main():
    """メイン実行"""
    print("🚀 v3戦略分析を開始します...")

    # データ読み込み
    test_data = load_test_data()
    sft_datasets = load_sft_datasets()
    inference_maps = {
        'v0': load_inference_data('v0'),
        'v1': load_inference_data('v1'),
        'v2': load_inference_data('v2'),
    }

    # 分析実行
    test_analysis = analyze_test_data(test_data)
    sft_analysis = analyze_sft_datasets(sft_datasets)
    inference_results = analyze_inference_results(test_data, inference_maps)

    # バージョン間比較
    compare_versions(test_data, inference_maps)

    # 戦略提案
    suggest_strategy(test_analysis, sft_analysis, inference_results)

    print("\n" + "="*60)
    print("✅ 分析完了")
    print("="*60)


if __name__ == "__main__":
    main()
