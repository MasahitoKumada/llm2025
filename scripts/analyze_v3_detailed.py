#!/usr/bin/env python3
"""
v3戦略詳細分析スクリプト

テストデータのタスク分布とSFTデータセットのタスク分布を比較し、
データ増減の具体的な戦略を提案する。
"""
import json
from collections import defaultdict
from pathlib import Path


def load_json(filepath):
    """JSONファイルを読込む"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def extract_task_type_from_messages(messages):
    """messagesからタスクタイプを推測する"""
    if not messages:
        return "Unknown"

    # システムプロンプトまたは最初のメッセージを確認
    for msg in messages:
        content = msg.get('content', '')
        if isinstance(content, str):
            content_lower = content.lower()
            # 入力形式と出力形式を検出
            for in_fmt in ['csv', 'json', 'yaml', 'xml', 'toml', 'text']:
                for out_fmt in ['csv', 'json', 'yaml', 'xml', 'toml']:
                    if in_fmt != out_fmt:
                        has_both = (
                            in_fmt in content_lower and
                            out_fmt in content_lower
                        )
                        if has_both:
                            return f"{in_fmt.upper()} to {out_fmt.upper()}"
    return "Unknown"


def analyze_sft_dataset_detail(dataset_path, dataset_name):
    """SFTデータセットの詳細分析"""
    data = load_json(dataset_path)

    # タスクタイプの分布
    task_types = defaultdict(int)

    # 出力形式の分布
    output_formats = defaultdict(int)

    # クエリ長の統計
    query_lengths = []

    # 問題パターンのカウント
    issues = {
        'has_code_block': 0,
        'has_explanation': 0,
    }

    for item in data:
        messages = item.get('messages', [])
        metadata = item.get('metadata', {})

        # タスクタイプを推測
        task_type = metadata.get('task_name', 'Unknown')
        if task_type == 'Unknown':
            task_type = extract_task_type_from_messages(messages)
        task_types[task_type] += 1

        # 出力形式
        output_type = metadata.get('output_type', 'Unknown')
        output_formats[output_type] += 1

        # アシスタントの応答を確認
        for msg in messages:
            if msg.get('role') == 'assistant':
                content = msg.get('content', '')
                if '```' in content:
                    issues['has_code_block'] += 1
                if "Here's" in content or 'Let me' in content:
                    issues['has_explanation'] += 1

            if msg.get('role') == 'user':
                content = msg.get('content', '')
                if isinstance(content, str):
                    query_lengths.append(len(content))

    return {
        'name': dataset_name,
        'total': len(data),
        'task_types': dict(task_types),
        'output_formats': dict(output_formats),
        'avg_query_length': (
            sum(query_lengths) / len(query_lengths) if query_lengths else 0
        ),
        'issues': issues
    }


def analyze_problem_cases(test_data, v0_data, v2_data):
    """問題のあるケースを詳細分析"""
    v0_map = {item['task_id']: item['generation'] for item in v0_data}
    v2_map = {item['task_id']: item['generation'] for item in v2_data}

    problem_cases = []

    for item in test_data:
        task_id = item['task_id']
        task_name = item.get('task_name', 'Unknown')
        output_type = item.get('output_type', 'Unknown')

        v0_gen = v0_map.get(task_id, '')
        v2_gen = v2_map.get(task_id, '')

        # 両方に問題がある場合
        v0_has_issue = (
            '```' in v0_gen or
            "Here's" in v0_gen or
            'Let me' in v0_gen
        )
        v2_has_issue = (
            '```' in v2_gen or
            "Here's" in v2_gen or
            'Let me' in v2_gen
        )

        if v0_has_issue and v2_has_issue:
            problem_cases.append({
                'task_id': task_id,
                'task_name': task_name,
                'output_type': output_type,
                'query_preview': item.get('query', '')[:200],
                'v0_preview': v0_gen[:200],
                'v2_preview': v2_gen[:200]
            })

    return problem_cases


def compare_distributions(test_task_dist, sft_task_dist):
    """テストデータとSFTデータのタスク分布を比較"""
    all_tasks = set(test_task_dist.keys()) | set(sft_task_dist.keys())

    comparison = []
    for task in sorted(all_tasks):
        test_count = test_task_dist.get(task, 0)
        sft_count = sft_task_dist.get(task, 0)
        comparison.append({
            'task': task,
            'test_count': test_count,
            'sft_count': sft_count,
            'ratio': sft_count / test_count if test_count > 0 else float('inf')
        })

    return comparison


def main():
    """メイン処理"""
    import sys

    output_file = "outputs/v3_detailed_analysis.txt"
    with open(output_file, 'w', encoding='utf-8') as f:
        old_stdout = sys.stdout
        sys.stdout = f

        # データ読み込み
        test_data = load_json("test_data/public_150.json")
        v0_data = load_json("outputs/inference_v0.json")
        v2_data = load_json("outputs/inference_v2.json")

        # テストデータのタスク分布
        test_task_dist = defaultdict(int)
        for item in test_data:
            test_task_dist[item.get('task_name', 'Unknown')] += 1

        print("=" * 70)
        print("詳細分析: v3戦略のためのデータ増減検討")
        print("=" * 70)

        # 1. SFTデータセットの詳細分析
        print("\n" + "=" * 70)
        print("1. 各SFTデータセットの詳細分析")
        print("=" * 70)

        sft_dir = Path("inputs/sft")
        all_sft_task_dist = defaultdict(int)

        for dataset_dir in sorted(sft_dir.iterdir()):
            if dataset_dir.is_dir():
                train_json = dataset_dir / "train.json"
                if train_json.exists():
                    result = analyze_sft_dataset_detail(
                        train_json, dataset_dir.name
                    )
                    print(f"\n■ {result['name']} ({result['total']} 件)")
                    print("  タスクタイプ分布:")
                    for task, count in sorted(
                        result['task_types'].items(),
                        key=lambda x: -x[1]
                    ):
                        print(f"    {task}: {count}")
                        all_sft_task_dist[task] += count
                    print("  問題パターン:")
                    print(f"    コードブロック: {result['issues']['has_code_block']}")
                    expl = result['issues']['has_explanation']
                    print(f"    説明テキスト: {expl}")

        # 2. テストvsトレーニングの分布比較
        print("\n" + "=" * 70)
        print("2. テストデータ vs SFTデータ タスク分布比較")
        print("=" * 70)

        comparison = compare_distributions(
            dict(test_task_dist), dict(all_sft_task_dist)
        )

        print("\n■ カバレッジ分析（テストデータのタスクがSFTでどれだけカバーされているか）")
        print("-" * 70)
        header = "タスク名                | テスト | SFT    | 比率"
        print(header)
        print("-" * 70)
        for item in sorted(comparison, key=lambda x: x['ratio']):
            task = item['task'][:22].ljust(22)
            test_c = str(item['test_count']).rjust(6)
            sft_c = str(item['sft_count']).rjust(6)
            ratio_val = item['ratio']
            if ratio_val == float('inf'):
                ratio_str = "∞".rjust(8)
            else:
                ratio_str = f"{ratio_val:.1f}".rjust(8)
            print(f"{task} | {test_c} | {sft_c} | {ratio_str}")

        # 3. 問題ケースの詳細分析
        print("\n" + "=" * 70)
        print("3. 両バージョンで問題があるケースの詳細")
        print("=" * 70)

        problem_cases = analyze_problem_cases(test_data, v0_data, v2_data)

        print(f"\n両バージョンで問題があるケース: {len(problem_cases)} 件")

        if problem_cases:
            print("\n■ 問題ケースのタスク名分布:")
            pc_dist = defaultdict(int)
            for pc in problem_cases:
                pc_dist[pc['task_name']] += 1
            for task, count in sorted(pc_dist.items(), key=lambda x: -x[1]):
                print(f"  {task}: {count} 件")

            print("\n■ 問題ケースのサンプル（最大5件）:")
            for i, pc in enumerate(problem_cases[:5]):
                print(f"\n--- ケース {i+1} ---")
                print(f"  task_id: {pc['task_id']}")
                print(f"  task_name: {pc['task_name']}")
                print(f"  output_type: {pc['output_type']}")
                print(f"  query_preview: {pc['query_preview'][:100]}...")

        # 4. 具体的な戦略提案
        print("\n" + "=" * 70)
        print("4. v3戦略: 具体的なデータ増減提案")
        print("=" * 70)

        print("\n■ 【増やすべきタスク】（テスト比率が低い）")
        under_covered = [
            c for c in comparison
            if c['test_count'] > 0 and c['ratio'] < 50
        ]
        for item in sorted(under_covered, key=lambda x: x['ratio']):
            task = item['task']
            test_c = item['test_count']
            sft_c = item['sft_count']
            ratio_v = item['ratio']
            target = test_c * 50  # テストの50倍を目標
            add = max(0, target - sft_c)
            print(f"  {task}:")
            print(f"    現状: テスト {test_c}件, SFT {sft_c}件 (比率 {ratio_v:.1f})")
            print(f"    推奨: +{add}件 追加して比率50以上に")

        print("\n■ 【減らす/品質改善すべきタスク】")
        print("  - コードブロック(```)を含む訓練データの修正")
        print("  - 説明テキスト(Here's, Let me)を含む訓練データの修正")
        print("  - 過剰なタスクタイプの削減（特にUnknown）")

        print("\n■ 【優先度の高い改善アクション】")
        print("  1. CSV to XML: v2で悪化（2件）→ 訓練データの品質確認")
        print("  2. CSV to YAML: 両方悪い（2件）→ 訓練データ追加/修正")
        print("  3. YAML to XML: 両方悪い（1件）→ 訓練データ追加/修正")
        print("  4. Text to TOML: テスト25件と多い → 十分な訓練データ確保")
        print("  5. 全体的にコードブロックと説明テキストを除去")

        print("\n" + "=" * 70)
        print("詳細分析完了")
        print("=" * 70)

        sys.stdout = old_stdout

    print(f"詳細分析結果を {output_file} に保存しました")


if __name__ == "__main__":
    main()
