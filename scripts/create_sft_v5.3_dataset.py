#!/usr/bin/env python3
"""
SFT v5.3 データセット作成スクリプト

v5.2データセットをベースに、エラーパターンに対応したターゲット訓練データを追加。
Empty Think Injectionを適用して、0.8+スコアを目指します。

入力:
- inputs/sft_processed/v5/train.json (v5.2ベースデータ)
- inputs/sft_processed/v5.3_targeted_samples/targeted_training_samples.json

出力: inputs/sft_processed/v5.3/train.json

改善ポイント:
1. TOMLエラーパターン対策（7件のエラーに対応）
   - inline tableは1行で完結
   - 配列テーブルは[[table]]構文
   - YAML構文混入防止
2. XMLエスケープ対策（1件のエラーに対応）
   - &amp;, &lt;, &gt; のエスケープ
3. Empty Think Injection適用
   - <think>\n</think>\n\n{data} 形式
"""
import json
import re
import copy
from pathlib import Path
from collections import defaultdict


def apply_empty_think_injection(content: str) -> str:
    """
    Empty Think Injectionを適用します。
    CoT部分を削除し、<think></think>を先頭に追加します。
    """
    # 出力部分を抽出するパターン
    output_patterns = [
        r'Output:\s*\n',
        r'OUTPUT:\s*\n',
        r'Final:\s*\n',
        r'Answer:\s*\n',
        r'Result:\s*\n',
        r'Response:\s*\n',
    ]

    result = content

    # CoTの"Output:"以降を抽出
    for pattern in output_patterns:
        match = re.search(pattern, result, re.IGNORECASE)
        if match:
            result = result[match.end():]
            break

    # マークダウンコードブロックの除去
    code_block_pattern = r'^```\w*\s*\n?(.*?)```\s*$'
    code_block_match = re.match(code_block_pattern, result.strip(), re.DOTALL)
    if code_block_match:
        result = code_block_match.group(1)

    # 前後の余計な説明文を除去
    prefixes_to_remove = [
        r'^Here\'?s?\s+(the|your|a)\s+.*?:\s*\n',
        r'^Sure[,!]?\s+.*?:\s*\n',
        r'^The\s+.*?:\s*\n',
        r'^Below\s+is\s+.*?:\s*\n',
    ]

    for prefix_pattern in prefixes_to_remove:
        result = re.sub(prefix_pattern, '', result, flags=re.IGNORECASE)

    result = result.strip()

    # Empty Think Injectionを適用
    return f"<think>\n</think>\n\n{result}"


def convert_targeted_sample_to_sft_format(sample: dict) -> dict:
    """
    ターゲットサンプルをSFTデータセット形式に変換します。
    """
    messages = sample['messages']
    output_format = sample.get('output_format', 'unknown')

    # systemメッセージを適切な形式に
    system_content = "You are an expert in structured data formats. Generate syntactically perfect output."

    # userメッセージを取得
    user_content = ""
    assistant_content = ""

    for msg in messages:
        if msg['role'] == 'user':
            user_content = msg['content']
        elif msg['role'] == 'assistant':
            assistant_content = msg['content']

    # Empty Think Injection適用
    assistant_with_think = f"<think>\n</think>\n\n{assistant_content}"

    return {
        "messages": [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content},
            {"role": "assistant", "content": assistant_with_think}
        ],
        "metadata": {
            "format": output_format,
            "type": "conversion",
            "source": "targeted_training_v5.3",
            "purpose": sample.get('purpose', '')
        }
    }


def get_format(sample: dict) -> str:
    """サンプルのフォーマットを取得"""
    return sample.get('metadata', {}).get('format', 'unknown').lower()


def main():
    """メイン処理"""
    # パス設定
    base_data_path = Path('inputs/sft_processed/v5/train.json')
    targeted_samples_path = Path('inputs/sft_processed/v5.3_targeted_samples/targeted_training_samples.json')
    output_dir = Path('inputs/sft_processed/v5.3')
    output_path = output_dir / 'train.json'

    # 入力ファイルの存在確認
    if not base_data_path.exists():
        print(f"❌ ベースデータが見つかりません: {base_data_path}")
        return

    if not targeted_samples_path.exists():
        print(f"❌ ターゲットサンプルが見つかりません: {targeted_samples_path}")
        return

    # 出力ディレクトリの作成
    output_dir.mkdir(parents=True, exist_ok=True)

    # ベースデータの読み込み
    print(f"📖 ベースデータ読み込み中: {base_data_path}")
    with open(base_data_path, 'r', encoding='utf-8') as f:
        base_data = json.load(f)

    original_count = len(base_data)
    print(f"   元のサンプル数: {original_count}")

    # ターゲットサンプルの読み込み
    print(f"📖 ターゲットサンプル読み込み中: {targeted_samples_path}")
    with open(targeted_samples_path, 'r', encoding='utf-8') as f:
        targeted_samples = json.load(f)

    print(f"   ターゲットサンプル数: {len(targeted_samples)}")

    # フォーマット別にベースデータを分類
    format_samples = defaultdict(list)
    for i, sample in enumerate(base_data):
        fmt = get_format(sample)
        format_samples[fmt].append((i, sample))

    print("\n📊 ベースデータのフォーマット別分布:")
    for fmt, samples in sorted(format_samples.items()):
        print(f"   {fmt}: {len(samples)} 件")

    # ============================================================
    # 1. Empty Think Injectionを全データに適用
    # ============================================================
    print("\n🔧 1. Empty Think Injection適用...")

    new_data = []
    injection_count = 0

    for sample in base_data:
        new_sample = copy.deepcopy(sample)

        # assistantメッセージを探してEmpty Think Injectionを適用
        for msg in new_sample['messages']:
            if msg['role'] == 'assistant':
                original_content = msg['content']

                # 既に<think>タグがある場合はスキップ
                if '<think>' not in original_content:
                    msg['content'] = apply_empty_think_injection(original_content)
                    injection_count += 1

        new_data.append(new_sample)

    print(f"   Empty Think Injection適用: {injection_count} 件")

    # ============================================================
    # 2. ターゲットサンプルを追加
    # ============================================================
    print("\n🔧 2. ターゲットサンプル追加...")

    toml_samples_added = 0
    xml_samples_added = 0

    for sample in targeted_samples:
        converted = convert_targeted_sample_to_sft_format(sample)
        new_data.append(converted)

        fmt = sample.get('output_format', '').lower()
        if fmt == 'toml':
            toml_samples_added += 1
        elif fmt == 'xml':
            xml_samples_added += 1

    print(f"   TOMLターゲットサンプル追加: +{toml_samples_added} 件")
    print(f"   XMLターゲットサンプル追加: +{xml_samples_added} 件")
    print(f"   合計追加: +{len(targeted_samples)} 件")

    # ============================================================
    # 最終統計
    # ============================================================
    print("\n" + "=" * 60)
    print("📊 最終統計")
    print("=" * 60)

    # 新しいフォーマット別分布
    new_format_counts = defaultdict(int)
    for sample in new_data:
        fmt = get_format(sample)
        new_format_counts[fmt] += 1

    print(f"\n元のサンプル数: {original_count}")
    print(f"新しいサンプル数: {len(new_data)}")
    print(f"増加数: +{len(new_data) - original_count}")

    print("\nフォーマット別の件数:")
    for fmt in ['toml', 'xml', 'yaml', 'json', 'csv', 'unknown']:
        if fmt in new_format_counts or fmt in ['toml', 'xml', 'yaml', 'json', 'csv']:
            original = len(format_samples.get(fmt, []))
            new = new_format_counts.get(fmt, 0)
            diff = new - original
            if diff != 0:
                print(f"   {fmt.upper()}: {original} → {new} (+{diff})")
            else:
                print(f"   {fmt.upper()}: {new}")

    print("\n追加内容の内訳:")
    print(f"   Empty Think Injection: {injection_count} 件に適用")
    print(f"   TOMLターゲットサンプル: +{toml_samples_added}")
    print(f"   XMLターゲットサンプル: +{xml_samples_added}")

    # ターゲットサンプルの詳細を表示
    print("\n📝 追加したターゲットサンプルの詳細:")
    for sample in targeted_samples:
        purpose = sample.get('purpose', 'N/A')
        fmt = sample.get('output_format', 'unknown').upper()
        print(f"   [{fmt}] {purpose}")

    # 出力
    print(f"\n💾 保存中: {output_path}")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(new_data, f, ensure_ascii=False, indent=2)

    print("\n✅ v5.3データセット作成完了!")
    print(f"   保存先: {output_path}")
    print(f"   サンプル数: {len(new_data)}")

    # v5.3の特徴まとめ
    print("\n" + "=" * 60)
    print("📋 v5.3の特徴")
    print("=" * 60)
    print("""
1. Empty Think Injection適用済み
   - <think>\\n</think>\\n\\n{data} 形式
   - 余計なCoTや説明文を削除

2. TOMLエラー対策サンプル追加（7件）
   - inline tableは1行で完結する例
   - [[配列テーブル]]構文の例
   - ネストされた構造の正しい表現

3. XMLエスケープ対策サンプル追加（3件）
   - &amp;, &lt;, &gt; のエスケープ例
   - 店舗名・商品名での&使用例

推奨ハイパラ（v5.2ベース、より保守的に）:
   - learning_rate: 3e-5〜4e-5
   - num_train_epochs: 1.5〜2
   - lora_r: 32〜64
   - lora_alpha: 32〜64
""")


if __name__ == '__main__':
    main()
