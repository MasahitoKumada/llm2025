#!/usr/bin/env python3
"""
SFT v6 データセット作成スクリプト

Empty Think Injection を適用したSFT v6データセットを作成します。
Qwen3の `<think>` 機能を逆利用し、空のthinkブロックで即座に構造化データを出力させます。

入力: inputs/sft_processed/v5/train.json
出力: inputs/sft_processed/v6/train.json

変換内容:
- assistant回答から「Approach:」セクションを除去
- assistant回答から「Output:」プレフィックスを除去
- 既存のマークダウンコードブロック（```json等）があれば除去
- 既存の説明文（"Sure! Here's..."等）があれば除去
- 先頭に `<think>\n</think>\n\n` を追加
"""
import json
import re
from pathlib import Path


def extract_pure_output(content: str) -> str:
    """
    assistant回答から純粋な構造化データ部分のみを抽出します。

    Args:
        content: 元のassistant回答

    Returns:
        純粋な構造化データ（TOML, CSV, JSON, XML, YAML等）
    """
    # Step 1: "Output:" 以降の部分を抽出
    # パターン: "Approach:...\n\nOutput:\n{data}" または "Output:\n{data}"
    output_patterns = [
        r'Output:\s*\n',  # "Output:\n" の後
        r'OUTPUT:\s*\n',  # 大文字版
        r'Final:\s*\n',   # "Final:\n" の後
        r'Answer:\s*\n',  # "Answer:\n" の後
        r'Result:\s*\n',  # "Result:\n" の後
        r'Response:\s*\n', # "Response:\n" の後
    ]

    result = content

    # マーカーを探して、それ以降を抽出
    for pattern in output_patterns:
        match = re.search(pattern, result, re.IGNORECASE)
        if match:
            result = result[match.end():]
            break

    # Step 2: マークダウンコードブロックの除去
    # パターン: ```json\n...\n``` または ```xml\n...\n``` など
    code_block_pattern = r'^```\w*\s*\n?(.*?)```\s*$'
    code_block_match = re.match(code_block_pattern, result.strip(), re.DOTALL)
    if code_block_match:
        result = code_block_match.group(1)

    # Step 3: 前後の余分な空白を整理（ただし、内部の改行は維持）
    result = result.strip()

    # Step 4: 一般的な説明文プレフィックスの除去
    prefixes_to_remove = [
        r"^Sure[!,.]?\s*(Here'?s?|is)?\s*(the)?\s*(output|result|data|response)?[:.!]?\s*\n*",
        r"^Here'?s?\s*(the)?\s*(output|result|data|response)?[:.!]?\s*\n*",
        r"^The\s+(output|result|data|response)\s+(is|follows)?[:.!]?\s*\n*",
        r"^Below\s+(is|you\s+can\s+find)\s+(the)?\s*(output|result|data)?[:.!]?\s*\n*",
    ]

    for prefix_pattern in prefixes_to_remove:
        result = re.sub(prefix_pattern, '', result, flags=re.IGNORECASE)

    return result.strip()


def apply_empty_think_injection(content: str) -> str:
    """
    Empty Think Injection を適用します。

    Args:
        content: 純粋な構造化データ

    Returns:
        `<think>\n</think>\n\n{content}` 形式の文字列
    """
    return f"<think>\n</think>\n\n{content}"


def convert_sample(sample: dict) -> dict:
    """
    1つのサンプルをv5形式からv6形式に変換します。

    Args:
        sample: v5形式のサンプル

    Returns:
        v6形式のサンプル
    """
    new_sample = sample.copy()
    new_messages = []

    for message in sample.get('messages', []):
        new_message = message.copy()

        if message.get('role') == 'assistant':
            # 純粋な構造化データを抽出
            pure_output = extract_pure_output(message['content'])
            # Empty Think Injection を適用
            new_content = apply_empty_think_injection(pure_output)
            new_message['content'] = new_content

        new_messages.append(new_message)

    new_sample['messages'] = new_messages
    return new_sample


def main():
    """メイン処理"""
    # パス設定
    input_path = Path('inputs/sft_processed/v5/train.json')
    output_dir = Path('inputs/sft_processed/v6')
    output_path = output_dir / 'train.json'

    # 入力ファイルの存在確認
    if not input_path.exists():
        print(f"❌ 入力ファイルが見つかりません: {input_path}")
        return

    # 出力ディレクトリの作成
    output_dir.mkdir(parents=True, exist_ok=True)

    # データの読み込み
    print(f"📖 読み込み中: {input_path}")
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"   サンプル数: {len(data)}")

    # 変換処理
    print("🔄 Empty Think Injection を適用中...")
    converted_data = []

    for i, sample in enumerate(data):
        converted_sample = convert_sample(sample)
        converted_data.append(converted_sample)

        # 進捗表示（500件ごと）
        if (i + 1) % 500 == 0:
            print(f"   処理済み: {i + 1} / {len(data)}")

    # 変換結果の確認（最初のサンプル）
    print("\n📋 変換例（最初のサンプル）:")
    print("-" * 50)
    original_content = data[0]['messages'][-1]['content']
    converted_content = converted_data[0]['messages'][-1]['content']

    print("【変換前（最初の200文字）】:")
    print(original_content[:200] + "...")
    print()
    print("【変換後（最初の200文字）】:")
    print(converted_content[:200] + "...")
    print("-" * 50)

    # 出力
    print(f"\n💾 保存中: {output_path}")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(converted_data, f, ensure_ascii=False, indent=2)

    # 統計情報
    print(f"\n✅ 変換完了!")
    print(f"   入力: {len(data)} サンプル")
    print(f"   出力: {len(converted_data)} サンプル")
    print(f"   保存先: {output_path}")

    # Empty Think Injection の確認
    think_prefix = "<think>\n</think>\n\n"
    has_think = sum(1 for s in converted_data
                   if s['messages'][-1]['content'].startswith(think_prefix))
    print(f"   Empty Think適用数: {has_think} / {len(converted_data)}")


if __name__ == '__main__':
    main()
