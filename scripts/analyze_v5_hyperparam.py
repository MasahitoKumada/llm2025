#!/usr/bin/env python3
"""
v5ハイパーパラメータ分析スクリプト

v5のスコア（0.739812）がv2（0.75074）を下回った原因を分析し、
ハイパーパラメータ調整の方向性を提案する。

WandBグラフからの観察:
- train/loss: 1.8から0.8まで下降、最後に少し上昇（1.1付近）
- eval/loss: 1.25から0.85まで下降、安定
- train/learning_rate: 0→5e-6→0（warmup 10%後に線形減衰）
- train/grad_norm: 初期5から1付近に安定
- train/epoch: 0→2（2エポック完了）
"""
import json
from collections import Counter, defaultdict


def load_json(path: str):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def analyze_output_quality(data: list, name: str):
    """出力の品質を分析"""
    print(f"\n=== {name} 出力品質分析 ===")

    empty_count = 0
    short_count = 0  # 50文字未満
    total_len = 0

    for item in data:
        output = item.get('output', '')
        if not output:
            empty_count += 1
        elif len(output) < 50:
            short_count += 1
        total_len += len(output) if output else 0

    avg_len = total_len / len(data) if data else 0
    print(f"  総数: {len(data)}件")
    print(f"  空出力: {empty_count}件 ({empty_count/len(data)*100:.1f}%)")
    print(f"  短出力(<50文字): {short_count}件 ({short_count/len(data)*100:.1f}%)")
    print(f"  平均出力長: {avg_len:.0f}文字")

    return {
        'total': len(data),
        'empty': empty_count,
        'short': short_count,
        'avg_len': avg_len
    }


def compare_outputs_by_task(test_data: list, v2_data: list, v5_data: list):
    """タスク別に出力を比較"""
    print("\n=== タスク別出力比較 ===")

    # task_idでインデックス化
    test_by_id = {item['task_id']: item for item in test_data}
    v2_by_id = {item['task_id']: item for item in v2_data}
    v5_by_id = {item['task_id']: item for item in v5_data}

    # タスク別に集計
    task_stats = defaultdict(lambda: {'v2_better': 0, 'v5_better': 0, 'same': 0, 'total': 0})

    for task_id, test_item in test_by_id.items():
        task_name = test_item.get('task_name', 'unknown')

        v2_output = v2_by_id.get(task_id, {}).get('output', '')
        v5_output = v5_by_id.get(task_id, {}).get('output', '')

        v2_len = len(v2_output) if v2_output else 0
        v5_len = len(v5_output) if v5_output else 0

        task_stats[task_name]['total'] += 1

        # 長さの差で簡易比較（実際のスコアは分からないので）
        if v2_len > v5_len * 1.2:
            task_stats[task_name]['v2_better'] += 1
        elif v5_len > v2_len * 1.2:
            task_stats[task_name]['v5_better'] += 1
        else:
            task_stats[task_name]['same'] += 1

    print("\nタスク名 | 総数 | v2優勢 | v5優勢 | 同等")
    print("-" * 60)
    for task_name in sorted(task_stats.keys()):
        stats = task_stats[task_name]
        print(f"{task_name:20s} | {stats['total']:3d} | {stats['v2_better']:3d} | {stats['v5_better']:3d} | {stats['same']:3d}")


def analyze_overfitting_signs(v2_data: list, v5_data: list, test_data: list):
    """過学習の兆候を分析"""
    print("\n=== 過学習兆候分析 ===")

    # 出力の多様性を確認
    v2_unique = len(set(item.get('output', '')[:100] for item in v2_data))
    v5_unique = len(set(item.get('output', '')[:100] for item in v5_data))

    print(f"  v2 ユニーク出力パターン（先頭100文字）: {v2_unique}")
    print(f"  v5 ユニーク出力パターン（先頭100文字）: {v5_unique}")

    # 特定のパターンの繰り返しを確認
    v2_starts = Counter(item.get('output', '')[:20] for item in v2_data if item.get('output'))
    v5_starts = Counter(item.get('output', '')[:20] for item in v5_data if item.get('output'))

    print("\n  v2 最頻出パターン（先頭20文字）:")
    for pattern, count in v2_starts.most_common(5):
        if count > 1:
            print(f"    '{pattern[:30]}...' x {count}")

    print("\n  v5 最頻出パターン（先頭20文字）:")
    for pattern, count in v5_starts.most_common(5):
        if count > 1:
            print(f"    '{pattern[:30]}...' x {count}")


def suggest_hyperparam_adjustments():
    """ハイパーパラメータ調整の提案"""
    print("\n" + "=" * 70)
    print("ハイパーパラメータ調整提案")
    print("=" * 70)

    print("""
【WandBグラフからの観察】

1. train/loss曲線:
   - 1.8 → 0.8まで順調に下降
   - 最後（step 400以降）で少し上昇（0.8 → 1.1）
   → 過学習の兆候？または学習終盤の不安定性

2. eval/loss曲線:
   - 1.25 → 0.85まで順調に下降
   - 最後まで下降傾向を維持
   → 過学習ではない可能性

3. learning_rate曲線:
   - warmup 10%後にピーク（5e-6）
   - その後線形減衰で0へ
   → 標準的なスケジュール

4. grad_norm曲線:
   - 初期: 5付近で不安定
   - step 100以降: 1付近で安定
   → 学習は安定している

【問題の仮説】

A. Epoch=2が過剰（v2はEpoch=1で0.75074達成）
   - 2エポック目で過学習した可能性
   - 最後のtrain/loss上昇がその証拠かも

B. データ変更（XMLエラー除去）が影響
   - 64件除去したが、それが重要なデータだった可能性
   - ただし、割合は1.6%と小さい

C. 他の要因
   - 推論時の設定（temperature, top_p等）
   - プロンプトの変更

【v6への提案】

1. 【推奨】Epoch=1に戻す
   - v2と同じ設定に戻し、XMLエラー除去の効果のみを確認
   - 期待: 0.75以上

2. 【オプション】Learning Rate下げる
   - 5e-6 → 2e-6 または 1e-6
   - より安定した学習を期待

3. 【オプション】Warmup比率を増やす
   - 10% → 15% または 20%
   - 初期の不安定性を軽減

4. 【オプション】Gradient Accumulation増やす
   - 8 → 16
   - 効果的なバッチサイズを増やして安定化

5. 【非推奨】Epoch=3以上
   - 過学習リスクが高い

【推奨するv6設定】

| パラメータ | v2 | v5 | v6提案 |
|---|---|---|---|
| データ件数 | 3,933 | 3,869 | 3,869 (v5と同じ) |
| Epoch | 1 | 2 | **1** |
| Learning Rate | 5e-6 | 5e-6 | 5e-6 |
| MAX_SEQ_LEN | 1024 | 1024 | 1024 |
| LoRA r | 64 | 64 | 64 |
| LoRA alpha | 128 | 128 | 128 |

基本的にv2の設定に戻し、データのみv5（XMLエラー除去済み）を使用。
""")


def main():
    print("=" * 70)
    print("v5ハイパーパラメータ分析")
    print("=" * 70)

    print("\nスコア推移:")
    print("  v0: 0.69426")
    print("  v1: 0.59555 (過学習)")
    print("  v2: 0.75074 (最高)")
    print("  v3: 0.72586 (データ増で悪化)")
    print("  v4: 0.74649")
    print("  v4.1: 0.734385 (データ削減で悪化)")
    print("  v5: 0.739812 (Epoch=2で悪化)")

    # データ読み込み
    test_data = load_json('test_data/public_150.json')
    v2_data = load_json('outputs/inference_v2.json')
    v5_data = load_json('outputs/inference_v5.json')

    # 出力品質分析
    v2_stats = analyze_output_quality(v2_data, 'v2')
    v5_stats = analyze_output_quality(v5_data, 'v5')

    # タスク別比較
    compare_outputs_by_task(test_data, v2_data, v5_data)

    # 過学習兆候分析
    analyze_overfitting_signs(v2_data, v5_data, test_data)

    # ハイパーパラメータ調整提案
    suggest_hyperparam_adjustments()


if __name__ == '__main__':
    main()
