#!/usr/bin/env python3
"""v2とv5の推論結果を比較分析"""
import json
from collections import Counter


def load_json(path):
    with open(path, 'r') as f:
        return json.load(f)


def main():
    test_data = load_json('test_data/public_150.json')
    v2_data = load_json('outputs/inference_v2.json')
    v5_data = load_json('outputs/inference_v5.json')

    # task_idでインデックス化
    test_by_id = {item['task_id']: item for item in test_data}
    v2_by_id = {item['task_id']: item for item in v2_data}
    v5_by_id = {item['task_id']: item for item in v5_data}

    print("=" * 70)
    print("v2 vs v5 出力比較分析")
    print("=" * 70)

    # 出力長の統計
    v2_lens = [len(item.get('generation', '')) for item in v2_data]
    v5_lens = [len(item.get('generation', '')) for item in v5_data]

    print(f"\n=== 出力長統計 ===")
    v2_avg = sum(v2_lens) / len(v2_lens)
    v5_avg = sum(v5_lens) / len(v5_lens)
    print(f"v2: 平均{v2_avg:.0f}文字, 最小{min(v2_lens)}, 最大{max(v2_lens)}")
    print(f"v5: 平均{v5_avg:.0f}文字, 最小{min(v5_lens)}, 最大{max(v5_lens)}")

    # タスク別に比較
    print(f"\n=== タスク別出力長比較 ===")
    task_diffs = {}
    for task_id, test_item in test_by_id.items():
        task_name = test_item.get('task_name', 'unknown')
        v2_len = len(v2_by_id.get(task_id, {}).get('generation', ''))
        v5_len = len(v5_by_id.get(task_id, {}).get('generation', ''))

        if task_name not in task_diffs:
            task_diffs[task_name] = {'v2_total': 0, 'v5_total': 0, 'count': 0}
        task_diffs[task_name]['v2_total'] += v2_len
        task_diffs[task_name]['v5_total'] += v5_len
        task_diffs[task_name]['count'] += 1

    print("\nタスク名                 | 件数 | v2平均 | v5平均 | 差分")
    print("-" * 70)
    for task_name in sorted(task_diffs.keys()):
        stats = task_diffs[task_name]
        v2_avg = stats['v2_total'] / stats['count']
        v5_avg = stats['v5_total'] / stats['count']
        diff = v5_avg - v2_avg
        diff_str = f"+{diff:.0f}" if diff >= 0 else f"{diff:.0f}"
        print(f"{task_name:24s} | {stats['count']:4d} | {v2_avg:6.0f} | "
              f"{v5_avg:6.0f} | {diff_str}")

    # 完全一致の数
    same_output = sum(
        1 for task_id in test_by_id
        if v2_by_id.get(task_id, {}).get('generation', '') ==
           v5_by_id.get(task_id, {}).get('generation', '')
    )
    print(f"\n完全一致: {same_output}/150 ({same_output/150*100:.1f}%)")

    # コードフェンス/前置き文の統計
    v2_codefence = sum(
        1 for item in v2_data if '```' in item.get('generation', '')
    )
    v5_codefence = sum(
        1 for item in v5_data if '```' in item.get('generation', '')
    )
    prefixes = ('Here', 'The', 'Below', 'I ')
    v2_prefix = sum(
        1 for item in v2_data
        if item.get('generation', '').strip().startswith(prefixes)
    )
    v5_prefix = sum(
        1 for item in v5_data
        if item.get('generation', '').strip().startswith(prefixes)
    )

    print(f"\n=== 問題パターン統計 ===")
    print(f"コードフェンス: v2={v2_codefence}件, v5={v5_codefence}件")
    print(f"前置き文: v2={v2_prefix}件, v5={v5_prefix}件")


if __name__ == '__main__':
    main()
