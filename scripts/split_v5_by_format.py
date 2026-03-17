#!/usr/bin/env python3
"""
v5データをフォーマット別に分割するスクリプト

Sequential SFT戦略（Person Uアプローチ）用のデータ準備
"""
import json
from pathlib import Path


def detect_format(item):
    """messagesからフォーマットを検出"""
    user_msg = item['messages'][0]['content'].lower() if item['messages'] else ''
    assistant_msg = item['messages'][1]['content'] if len(item['messages']) > 1 else ''

    # ユーザーメッセージからフォーマット指定を検出
    if 'json' in user_msg:
        return 'json'
    elif 'yaml' in user_msg or 'yml' in user_msg:
        return 'yaml'
    elif 'toml' in user_msg:
        return 'toml'
    elif 'xml' in user_msg:
        return 'xml'
    elif 'csv' in user_msg:
        return 'csv'

    # アシスタント出力から推測（フォールバック）
    assistant_start = assistant_msg.strip()[:50] if assistant_msg else ''
    if assistant_start.startswith('{') or assistant_start.startswith('['):
        return 'json'
    elif assistant_start.startswith('<'):
        return 'xml'
    elif '---' in assistant_start or ':' in assistant_start[:20]:
        return 'yaml'
    elif '=' in assistant_start[:20] and '[' in assistant_start:
        return 'toml'

    return 'unknown'


def split_by_format(input_path: str, output_dir: str):
    """v5データをフォーマット別に分割"""

    # 出力ディレクトリ作成
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # データ読み込み
    print(f"📂 入力ファイル: {input_path}")
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"   総件数: {len(data)}")

    # フォーマット別に分類
    format_data = {
        'json': [],
        'yaml': [],
        'toml': [],
        'xml': [],
        'csv': [],
        'unknown': []
    }

    for item in data:
        fmt = detect_format(item)
        format_data[fmt].append(item)

    # 統計表示
    print("\n📊 フォーマット別件数:")
    print("-" * 40)
    for fmt in ['json', 'yaml', 'toml', 'xml', 'csv', 'unknown']:
        count = len(format_data[fmt])
        pct = count / len(data) * 100
        print(f"   {fmt.upper():8}: {count:5} 件 ({pct:5.1f}%)")

    # 各フォーマットのデータを保存
    print("\n💾 ファイル出力:")
    for fmt in ['json', 'yaml', 'toml', 'xml', 'csv']:
        if format_data[fmt]:
            output_file = output_path / f"v5_{fmt}.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(format_data[fmt], f, ensure_ascii=False, indent=2)
            print(f"   ✅ {output_file} ({len(format_data[fmt])} 件)")

    # Sequential SFT用の組み合わせデータを作成
    print("\n🔧 Sequential SFT用データセット作成:")

    # Stage 1: JSON + CSV
    stage1_data = format_data['json'] + format_data['csv']
    stage1_file = output_path / "v5_stage1_json_csv.json"
    with open(stage1_file, 'w', encoding='utf-8') as f:
        json.dump(stage1_data, f, ensure_ascii=False, indent=2)
    print(f"   ✅ Stage 1 (JSON+CSV): {stage1_file} ({len(stage1_data)} 件)")

    # Stage 2: YAML のみ（v16.1モデルをベースにYAMLを追加学習）
    stage2_file = output_path / "v5_stage2_yaml.json"
    with open(stage2_file, 'w', encoding='utf-8') as f:
        json.dump(format_data['yaml'], f, ensure_ascii=False, indent=2)
    print(f"   ✅ Stage 2 (YAML): {stage2_file} ({len(format_data['yaml'])} 件)")

    # Stage 3: XML のみ
    stage3_file = output_path / "v5_stage3_xml.json"
    with open(stage3_file, 'w', encoding='utf-8') as f:
        json.dump(format_data['xml'], f, ensure_ascii=False, indent=2)
    print(f"   ✅ Stage 3 (XML): {stage3_file} ({len(format_data['xml'])} 件)")

    # Stage 4: TOML のみ
    stage4_file = output_path / "v5_stage4_toml.json"
    with open(stage4_file, 'w', encoding='utf-8') as f:
        json.dump(format_data['toml'], f, ensure_ascii=False, indent=2)
    print(f"   ✅ Stage 4 (TOML): {stage4_file} ({len(format_data['toml'])} 件)")

    # サマリー
    print("\n" + "=" * 60)
    print("📋 Sequential SFT ステージサマリー:")
    print("=" * 60)
    print(f"""
    Stage 1: JSON + CSV  → {len(stage1_data):,} 件
    Stage 2: YAML        → {len(format_data['yaml']):,} 件
    Stage 3: XML         → {len(format_data['xml']):,} 件
    Stage 4: TOML        → {len(format_data['toml']):,} 件
    ─────────────────────────────
    合計                 → {len(data):,} 件
    """)

    return format_data


if __name__ == "__main__":
    # v5データを分割
    input_path = "inputs/sft_processed/v5/train.json"
    output_dir = "inputs/sft_processed/v16_sequential"

    split_by_format(input_path, output_dir)

    print("\n✅ 完了！")
    print(f"   出力先: {output_dir}")
