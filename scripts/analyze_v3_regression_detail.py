#!/usr/bin/env python3
"""
v3リグレッション詳細分析

品質問題は減少しているのにスコアが下がった原因を深掘りする。
特に出力長が大きく変わったケースと、出力内容の変化を分析する。
"""
import json
import re
from pathlib import Path
from collections import defaultdict

BASE_DIR = Path(__file__).parent.parent
TEST_DATA_PATH = BASE_DIR / "test_data" / "public_150.json"
OUTPUTS_DIR = BASE_DIR / "outputs"


def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def extract_actual_output(generation, expected_format):
    """実際の出力部分を抽出（マークダウン除去等）"""
    # マークダウンコードブロックを除去
    if '```' in generation:
        pattern = r'```(?:json|yaml|toml|xml|csv)?\s*(.*?)\s*```'
        match = re.search(pattern, generation, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()

    # 説明文を除去して最初の構造化データを抽出
    lines = generation.split('\n')
    start_idx = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(('{', '[', '<', '---')):
            start_idx = i
            break
        if re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*\s*=', stripped):
            start_idx = i
            break

    return '\n'.join(lines[start_idx:]).strip()


def count_structure_elements(output, fmt):
    """構造化データの要素数をカウント"""
    if fmt == 'JSON':
        try:
            data = json.loads(output)
            return count_json_elements(data)
        except json.JSONDecodeError:
            return -1
    return len(output)


def count_json_elements(obj, depth=0):
    """JSONオブジェクトの要素数を再帰的にカウント"""
    if isinstance(obj, dict):
        count = len(obj)
        for v in obj.values():
            count += count_json_elements(v, depth + 1)
        return count
    elif isinstance(obj, list):
        count = len(obj)
        for item in obj:
            count += count_json_elements(item, depth + 1)
        return count
    return 0


def analyze_output_structure(test_data, v2_data, v3_data):
    """出力構造の詳細比較"""
    test_map = {item['task_id']: item for item in test_data}
    v2_map = {item['task_id']: item for item in v2_data}
    v3_map = {item['task_id']: item for item in v3_data}

    analysis = []

    for task_id, test_item in test_map.items():
        task_name = test_item.get('task_name', 'unknown')
        expected_format = test_item.get('output_type', 'JSON')

        v2_gen = v2_map.get(task_id, {}).get('generation', '')
        v3_gen = v3_map.get(task_id, {}).get('generation', '')

        v2_extracted = extract_actual_output(v2_gen, expected_format)
        v3_extracted = extract_actual_output(v3_gen, expected_format)

        v2_elements = count_structure_elements(v2_extracted, expected_format)
        v3_elements = count_structure_elements(v3_extracted, expected_format)

        v2_len = len(v2_gen)
        v3_len = len(v3_gen)

        analysis.append({
            'task_id': task_id,
            'task_name': task_name,
            'format': expected_format,
            'v2_len': v2_len,
            'v3_len': v3_len,
            'v2_extracted_len': len(v2_extracted),
            'v3_extracted_len': len(v3_extracted),
            'v2_elements': v2_elements,
            'v3_elements': v3_elements,
            'length_ratio': v3_len / v2_len if v2_len > 0 else 0,
            'element_ratio': v3_elements / v2_elements if v2_elements > 0 else 0,
            'v2_has_markdown': '```' in v2_gen,
            'v3_has_markdown': '```' in v3_gen,
            'v2_has_explanation': bool(re.search(
                r"(Here's|This is|Below|Notes:|Let me)", v2_gen)),
            'v3_has_explanation': bool(re.search(
                r"(Here's|This is|Below|Notes:|Let me)", v3_gen)),
        })

    return analysis


def print_detailed_samples(test_data, v2_data, v3_data, task_ids):
    """詳細なサンプル出力を表示"""
    test_map = {item['task_id']: item for item in test_data}
    v2_map = {item['task_id']: item for item in v2_data}
    v3_map = {item['task_id']: item for item in v3_data}

    for task_id in task_ids:
        test_item = test_map.get(task_id, {})
        v2_gen = v2_map.get(task_id, {}).get('generation', '')
        v3_gen = v3_map.get(task_id, {}).get('generation', '')

        print(f"\n{'='*80}")
        print(f"Task ID: {task_id}")
        print(f"Task Name: {test_item.get('task_name', 'unknown')}")
        print(f"Expected Format: {test_item.get('output_type', 'unknown')}")
        print(f"{'='*80}")

        print("\n--- Query (最初の300文字) ---")
        query = test_item.get('query', '')
        print(query[:300])

        print(f"\n--- v2 Output ({len(v2_gen)}文字) ---")
        print(v2_gen[:800])

        print(f"\n--- v3 Output ({len(v3_gen)}文字) ---")
        print(v3_gen[:800])


def main():
    print("=" * 80)
    print("v3リグレッション詳細分析")
    print("=" * 80)

    test_data = load_json(TEST_DATA_PATH)
    v2_data = load_json(OUTPUTS_DIR / "inference_v2.json")
    v3_data = load_json(OUTPUTS_DIR / "inference_v3.json")

    analysis = analyze_output_structure(test_data, v2_data, v3_data)

    # 統計
    print("\n📊 全体統計")
    print("-" * 40)

    # マークダウン除去後の出力長比較
    total = len(analysis)
    v2_ext_sum = sum(a['v2_extracted_len'] for a in analysis)
    v3_ext_sum = sum(a['v3_extracted_len'] for a in analysis)
    v2_extracted_avg = v2_ext_sum / total
    v3_extracted_avg = v3_ext_sum / total

    print("抽出後平均出力長:")
    print(f"  v2: {v2_extracted_avg:.0f}文字")
    print(f"  v3: {v3_extracted_avg:.0f}文字")
    print(f"  差分: {v3_extracted_avg - v2_extracted_avg:+.0f}文字")

    # 要素数比較
    v2_elem_list = [a['v2_elements'] for a in analysis if a['v2_elements'] > 0]
    v3_elem_list = [a['v3_elements'] for a in analysis if a['v3_elements'] > 0]
    valid_count = sum(
        1 for a in analysis
        if a['v2_elements'] > 0 and a['v3_elements'] > 0
    )

    if valid_count > 0:
        v2_elements_avg = sum(v2_elem_list)
        v3_elements_avg = sum(v3_elem_list)
        print(f"\nJSON要素数（解析可能な{valid_count}件）:")
        print(f"  v2平均: {v2_elements_avg/valid_count:.1f}要素")
        print(f"  v3平均: {v3_elements_avg/valid_count:.1f}要素")

    # タスクタイプ別の変化
    print("\n📈 タスクタイプ別の出力長変化")
    print("-" * 40)

    by_task = defaultdict(list)
    for a in analysis:
        by_task[a['task_name']].append(a)

    for task_name, items in sorted(by_task.items()):
        v2_avg = sum(i['v2_len'] for i in items) / len(items)
        v3_avg = sum(i['v3_len'] for i in items) / len(items)
        diff_pct = (v3_avg - v2_avg) / v2_avg * 100 if v2_avg > 0 else 0

        if diff_pct > 20:
            indicator = "🔺"
        elif diff_pct < -20:
            indicator = "🔻"
        else:
            indicator = "➡️"
        print(f"{indicator} {task_name}: {v2_avg:.0f} → {v3_avg:.0f} "
              f"({diff_pct:+.1f}%)")

    # 極端なケースの詳細分析
    print("\n📝 極端に出力が変化したケースの詳細")
    print("-" * 40)

    # 極端に短くなったケース
    short_cases = sorted(
        [a for a in analysis if a['length_ratio'] < 0.5 and a['v2_len'] > 100],
        key=lambda x: x['length_ratio']
    )[:5]

    # 極端に長くなったケース
    long_cases = sorted(
        [a for a in analysis if a['length_ratio'] > 2.0 and a['v2_len'] > 100],
        key=lambda x: -x['length_ratio']
    )[:5]

    print(f"\n🔻 極端に短くなったケース: {len(short_cases)}件")
    if short_cases:
        print_detailed_samples(
            test_data, v2_data, v3_data,
            [c['task_id'] for c in short_cases[:2]]
        )

    print(f"\n🔺 極端に長くなったケース: {len(long_cases)}件")
    if long_cases:
        print_detailed_samples(
            test_data, v2_data, v3_data,
            [c['task_id'] for c in long_cases[:2]]
        )

    # v3で説明文が増えたケース
    explanation_added = [
        a for a in analysis
        if a['v3_has_explanation'] and not a['v2_has_explanation']
    ]

    print(f"\n⚠️ v3で説明文が追加されたケース: {len(explanation_added)}件")
    if explanation_added:
        for case in explanation_added[:5]:
            print(f"  - {case['task_id']} ({case['task_name']})")

    # v3でマークダウンが除去されたケース
    markdown_removed = [
        a for a in analysis
        if a['v2_has_markdown'] and not a['v3_has_markdown']
    ]

    print(f"\n✅ v3でマークダウンが除去されたケース: {len(markdown_removed)}件")

    # 仮説：スコア低下の原因
    print("\n" + "=" * 80)
    print("💡 スコア低下の原因仮説")
    print("=" * 80)

    print("""
【観察された事実】
1. 品質問題（マークダウン・説明文）は減少している
2. 一部のタスクで出力が極端に変化している
3. 平均出力長は約4.6%増加

【仮説1: 出力形式の変化】
v3では「純粋な出力」を学習したが、評価システムが期待する形式と
微妙に異なる可能性がある。例えば：
- インデントやスペースの違い
- キーの順序の違い
- 数値の表現形式の違い

【仮説2: 過度な一般化】
データセットの変更により、特定のパターンへの適合が失われた可能性。
v2で正しく処理できていたケースがv3で失敗している。

【仮説3: 冗長な出力】
一部のケースで出力が極端に長くなっており、不要な情報が
追加されている可能性がある。

【v4への推奨】
1. v2のデータセットをベースに戻す
2. 品質フィルタリングは最小限に
3. 特定タスクへの過度な最適化を避ける
""")


if __name__ == "__main__":
    main()
