#!/usr/bin/env python3
"""
SFT v7.1 データセット作成スクリプト

v5データセット (3,869件) をベースに、バランス重視でデータを追加します。
v7では過学習リスクがあったため、TOMLのアップサンプリングを大幅に削減します。

入力: inputs/sft_processed/v5/train.json
出力: inputs/sft_processed/v7.1/train.json

改善内容:
1. TOMLアップサンプリング: +100件のみ（v7の+1,222件から大幅削減）
   - 複雑なTOML（インラインテーブル・配列テーブル含む）を優先的に追加
   - 元の611件 → 711件（約1.16倍）

2. XMLエスケープ学習データ追加: +8件（v7と同じ）
   - `&amp;`, `&lt;`, `&gt;` を含むサンプルを追加

3. Deep YAML アップサンプリング: +36件
   - depth >= 5 のサンプルを追加

期待されるサンプル数:
| フォーマット | v5 | v7.1 | 増加 |
|------------|-----|------|------|
| TOML | 611 | 711 | +100 |
| XML | 1,012 | 1,020 | +8 |
| YAML | 624 | 660 | +36 |
| JSON | 1,075 | 1,075 | 0 |
| CSV | 547 | 547 | 0 |
| 合計 | 3,869 | 4,013 | +144 |
"""
import json
import re
import copy
import xml.etree.ElementTree as ET
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple, Optional


# ============================================================
# 設定
# ============================================================
TOML_UPSAMPLE_COUNT = 100  # v7.1では100件のみ追加（v7では+1,222件だった）
YAML_DEEP_THRESHOLD = 5   # 深いYAMLの閾値（depth >= 5）


def extract_output_content(assistant_content: str) -> str:
    """
    assistant回答から構造化データ部分のみを抽出します。
    """
    output_patterns = [
        r'Output:\s*\n',
        r'OUTPUT:\s*\n',
        r'Final:\s*\n',
        r'Answer:\s*\n',
        r'Result:\s*\n',
        r'Response:\s*\n',
    ]

    result = assistant_content

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

    return result.strip()


def calculate_yaml_depth(yaml_content: str) -> int:
    """
    YAMLの最大深度を計算します（インデントベース）。
    """
    try:
        max_depth = 1
        lines = yaml_content.split('\n')
        for line in lines:
            if line.strip() and not line.strip().startswith('#'):
                # インデントレベルを計算（スペース2つ = 1レベル）
                stripped = line.lstrip()
                indent = len(line) - len(stripped)
                depth = (indent // 2) + 1
                max_depth = max(max_depth, depth)
        return max_depth
    except Exception:
        return 0


def calculate_toml_complexity(toml_content: str) -> Tuple[int, bool, bool]:
    """
    TOMLの複雑さを計算します。

    Returns:
        (depth, has_inline_table, has_array_of_tables)
    """
    depth = 1
    has_inline_table = '{' in toml_content and '}' in toml_content
    has_array_of_tables = '[[' in toml_content

    # テーブルヘッダーの深さを計算
    table_pattern = r'\[+([^\]]+)\]+'
    for match in re.finditer(table_pattern, toml_content):
        table_name = match.group(1)
        # ドット区切りの深さ
        table_depth = len(table_name.split('.'))
        depth = max(depth, table_depth)

    return depth, has_inline_table, has_array_of_tables


def get_format(sample: dict) -> str:
    """サンプルのフォーマットを取得"""
    return sample.get('metadata', {}).get('format', 'unknown').lower()


def create_xml_escape_samples() -> List[dict]:
    """
    XMLエスケープ文字を含むサンプルを作成します。
    """
    escape_samples = [
        # Sample 1: &amp; in text content
        {
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert in XML format. Think step-by-step, then generate syntactically perfect XML."
                },
                {
                    "role": "user",
                    "content": "Convert this JSON data to XML format:\n{\n  \"company\": \"Smith & Jones LLC\",\n  \"description\": \"Legal services & consulting\",\n  \"founded\": 2010\n}"
                },
                {
                    "role": "assistant",
                    "content": "Approach:\n1. Task: Convert company data from JSON to XML\n2. Complexity: simple - 3-5 fields, minimal nesting\n3. Format rules: well-formed tags, proper nesting, escaped special chars\n4. Key rule: & must be escaped as &amp; in XML\n5. Transform values to match the target format specifications.\n\nOutput:\n<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<company>\n<name>Smith &amp; Jones LLC</name>\n<description>Legal services &amp; consulting</description>\n<founded>2010</founded>\n</company>"
                }
            ],
            "metadata": {
                "format": "xml",
                "complexity": "simple",
                "schema": "company",
                "type": "conversion",
                "escape_chars": ["&amp;"]
            }
        },
        # Sample 2: &lt; and &gt; in text content
        {
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert in XML format. Think step-by-step, then generate syntactically perfect XML."
                },
                {
                    "role": "user",
                    "content": "Convert this JSON data to XML format:\n{\n  \"expression\": \"x < 10 && y > 5\",\n  \"result\": \"condition is true when x<10 and y>5\",\n  \"type\": \"boolean\"\n}"
                },
                {
                    "role": "assistant",
                    "content": "Approach:\n1. Task: Convert expression data from JSON to XML\n2. Complexity: simple - 3-5 fields, minimal nesting\n3. Format rules: well-formed tags, proper nesting, escaped special chars\n4. Key rule: < must be &lt;, > must be &gt;, & must be &amp;\n5. Transform values to match the target format specifications.\n\nOutput:\n<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<expression_data>\n<expression>x &lt; 10 &amp;&amp; y &gt; 5</expression>\n<result>condition is true when x&lt;10 and y&gt;5</result>\n<type>boolean</type>\n</expression_data>"
                }
            ],
            "metadata": {
                "format": "xml",
                "complexity": "simple",
                "schema": "expression",
                "type": "conversion",
                "escape_chars": ["&lt;", "&gt;", "&amp;"]
            }
        },
        # Sample 3: Mixed escapes in product data
        {
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert in XML format. Think step-by-step, then generate syntactically perfect XML."
                },
                {
                    "role": "user",
                    "content": "Generate a product catalog entry in XML format for a tech gadget."
                },
                {
                    "role": "assistant",
                    "content": "Approach:\n1. Task: Create product catalog in XML\n2. Complexity: medium - 5-8 fields, 2-3 levels\n3. Format rules: well-formed tags, proper nesting, escaped special chars\n4. Key rule: Special chars &, <, > must be properly escaped\n5. Populate fields with realistic example data.\n\nOutput:\n<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<product>\n<product_id>TECH-8834</product_id>\n<name>Pro &amp; Elite Headphones</name>\n<description>High-quality audio with frequency response &lt;20Hz to &gt;20kHz</description>\n<price currency=\"USD\">149.99</price>\n<specs>\n<battery>Up to 30 hours &amp; quick charge</battery>\n<connectivity>Bluetooth 5.0 &amp; wired</connectivity>\n</specs>\n<note>Rating: 4.5 &gt; average</note>\n</product>"
                }
            ],
            "metadata": {
                "format": "xml",
                "complexity": "medium",
                "schema": "product",
                "type": "generation",
                "escape_chars": ["&amp;", "&lt;", "&gt;"]
            }
        },
        # Sample 4: Escapes in attribute values (if applicable)
        {
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert in XML format. Think step-by-step, then generate syntactically perfect XML."
                },
                {
                    "role": "user",
                    "content": "Transform this JSON to XML:\n{\n  \"events\": [\n    {\"name\": \"Q&A Session\", \"time\": \"10:00\"},\n    {\"name\": \"Lunch & Networking\", \"time\": \"12:00\"}\n  ]\n}"
                },
                {
                    "role": "assistant",
                    "content": "Approach:\n1. Task: Convert events data from JSON to XML\n2. Complexity: medium - array of objects\n3. Format rules: well-formed tags, proper nesting, escaped special chars\n4. Key rule: & in text content must be escaped as &amp;\n5. Transform values to match the target format.\n\nOutput:\n<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<events>\n<event>\n<name>Q&amp;A Session</name>\n<time>10:00</time>\n</event>\n<event>\n<name>Lunch &amp; Networking</name>\n<time>12:00</time>\n</event>\n</events>"
                }
            ],
            "metadata": {
                "format": "xml",
                "complexity": "medium",
                "schema": "events",
                "type": "conversion",
                "escape_chars": ["&amp;"]
            }
        },
        # Sample 5: Code/formula with escapes
        {
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert in XML format. Think step-by-step, then generate syntactically perfect XML."
                },
                {
                    "role": "user",
                    "content": "Convert this JSON to XML:\n{\n  \"formula_id\": \"F001\",\n  \"name\": \"Comparison Check\",\n  \"expression\": \"if (a < b && c > d)\",\n  \"description\": \"Returns true when a<b and c>d\"\n}"
                },
                {
                    "role": "assistant",
                    "content": "Approach:\n1. Task: Convert formula data from JSON to XML\n2. Complexity: simple - 4 fields, minimal nesting\n3. Format rules: well-formed tags, escaped special chars\n4. Key rule: < becomes &lt;, > becomes &gt;, & becomes &amp;\n5. Transform values correctly.\n\nOutput:\n<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<formula>\n<formula_id>F001</formula_id>\n<name>Comparison Check</name>\n<expression>if (a &lt; b &amp;&amp; c &gt; d)</expression>\n<description>Returns true when a&lt;b and c&gt;d</description>\n</formula>"
                }
            ],
            "metadata": {
                "format": "xml",
                "complexity": "simple",
                "schema": "formula",
                "type": "conversion",
                "escape_chars": ["&lt;", "&gt;", "&amp;"]
            }
        },
        # Sample 6: Business with &
        {
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert in XML format. Think step-by-step, then generate syntactically perfect XML."
                },
                {
                    "role": "user",
                    "content": "Generate an XML document for a law firm's client record."
                },
                {
                    "role": "assistant",
                    "content": "Approach:\n1. Task: Create law firm client record in XML\n2. Complexity: medium - 6-8 fields, 2-3 levels\n3. Format rules: well-formed tags, escaped special chars\n4. Key rule: & in company names must be escaped as &amp;\n5. Populate with realistic legal industry data.\n\nOutput:\n<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<client_record>\n<client_id>CLT-29384</client_id>\n<firm_name>Johnson &amp; Associates</firm_name>\n<client_name>Roberts &amp; Co. Holdings</client_name>\n<case_type>Mergers &amp; Acquisitions</case_type>\n<status>Active</status>\n<notes>Client referred by Baker &amp; Miller LLP</notes>\n<billing>\n<rate>350</rate>\n<currency>USD</currency>\n</billing>\n</client_record>"
                }
            ],
            "metadata": {
                "format": "xml",
                "complexity": "medium",
                "schema": "client_record",
                "type": "generation",
                "escape_chars": ["&amp;"]
            }
        },
        # Sample 7: Scientific data with < and >
        {
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert in XML format. Think step-by-step, then generate syntactically perfect XML."
                },
                {
                    "role": "user",
                    "content": "Convert this JSON to XML:\n{\n  \"experiment_id\": \"EXP-442\",\n  \"temperature_range\": \"< 100°C\",\n  \"pressure_range\": \"> 1 atm\",\n  \"safety_note\": \"Handle with care when T > 80°C\"\n}"
                },
                {
                    "role": "assistant",
                    "content": "Approach:\n1. Task: Convert experiment data from JSON to XML\n2. Complexity: simple - 4 fields\n3. Format rules: well-formed tags, escaped special chars\n4. Key rule: < becomes &lt;, > becomes &gt;\n5. Transform scientific notation correctly.\n\nOutput:\n<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<experiment>\n<experiment_id>EXP-442</experiment_id>\n<temperature_range>&lt; 100°C</temperature_range>\n<pressure_range>&gt; 1 atm</pressure_range>\n<safety_note>Handle with care when T &gt; 80°C</safety_note>\n</experiment>"
                }
            ],
            "metadata": {
                "format": "xml",
                "complexity": "simple",
                "schema": "experiment",
                "type": "conversion",
                "escape_chars": ["&lt;", "&gt;"]
            }
        },
        # Sample 8: Programming tutorial with code snippets
        {
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert in XML format. Think step-by-step, then generate syntactically perfect XML."
                },
                {
                    "role": "user",
                    "content": "Create an XML document for a programming tutorial snippet."
                },
                {
                    "role": "assistant",
                    "content": "Approach:\n1. Task: Create programming tutorial in XML\n2. Complexity: medium - nested structure with code\n3. Format rules: well-formed tags, escaped special chars in code\n4. Key rule: Code operators <, >, & must be escaped\n5. Create realistic programming tutorial content.\n\nOutput:\n<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<tutorial>\n<tutorial_id>TUT-1045</tutorial_id>\n<title>Loops &amp; Conditionals</title>\n<lesson>\n<topic>For Loop Basics</topic>\n<code_example>for (i = 0; i &lt; 10; i++) { if (i &gt; 5 &amp;&amp; i &lt; 8) print(i); }</code_example>\n<explanation>Loop runs while i &lt; 10, prints when 5 &lt; i &lt; 8</explanation>\n</lesson>\n<difficulty>Beginner</difficulty>\n</tutorial>"
                }
            ],
            "metadata": {
                "format": "xml",
                "complexity": "medium",
                "schema": "tutorial",
                "type": "generation",
                "escape_chars": ["&lt;", "&gt;", "&amp;"]
            }
        },
    ]

    return escape_samples


def select_toml_samples_for_upsample(
    toml_samples: List[Tuple[int, dict]],
    target_count: int
) -> List[dict]:
    """
    TOMLサンプルから優先度順に target_count 件を選択します。

    優先度:
    1. インラインテーブル + 配列テーブル両方を持つ
    2. 配列テーブルのみを持つ
    3. インラインテーブルのみを持つ
    4. depth >= 2 のもの
    5. その他
    """
    # 複雑さでサンプルを分類
    priority_1 = []  # インライン + 配列テーブル
    priority_2 = []  # 配列テーブルのみ
    priority_3 = []  # インラインテーブルのみ
    priority_4 = []  # depth >= 2
    priority_5 = []  # その他

    for idx, sample in toml_samples:
        assistant_content = sample['messages'][-1]['content']
        output_content = extract_output_content(assistant_content)
        depth, has_inline, has_array_tables = calculate_toml_complexity(output_content)

        if has_inline and has_array_tables:
            priority_1.append((idx, sample, depth, has_inline, has_array_tables))
        elif has_array_tables:
            priority_2.append((idx, sample, depth, has_inline, has_array_tables))
        elif has_inline:
            priority_3.append((idx, sample, depth, has_inline, has_array_tables))
        elif depth >= 2:
            priority_4.append((idx, sample, depth, has_inline, has_array_tables))
        else:
            priority_5.append((idx, sample, depth, has_inline, has_array_tables))

    print(f"   優先度1（インライン+配列テーブル）: {len(priority_1)} 件")
    print(f"   優先度2（配列テーブルのみ）: {len(priority_2)} 件")
    print(f"   優先度3（インラインテーブルのみ）: {len(priority_3)} 件")
    print(f"   優先度4（depth >= 2）: {len(priority_4)} 件")
    print(f"   優先度5（その他）: {len(priority_5)} 件")

    # 優先度順に target_count 件を選択
    selected = []
    remaining = target_count

    for priority_group in [priority_1, priority_2, priority_3, priority_4, priority_5]:
        if remaining <= 0:
            break

        # 各優先度グループから選択
        for item in priority_group:
            if remaining <= 0:
                break
            selected.append(copy.deepcopy(item[1]))
            remaining -= 1

    # まだ足りない場合は、先頭から繰り返し選択
    if remaining > 0:
        all_samples = priority_1 + priority_2 + priority_3 + priority_4 + priority_5
        idx = 0
        while remaining > 0 and len(all_samples) > 0:
            selected.append(copy.deepcopy(all_samples[idx % len(all_samples)][1]))
            remaining -= 1
            idx += 1

    return selected


def main():
    """メイン処理"""
    # パス設定
    input_path = Path('inputs/sft_processed/v5/train.json')
    output_dir = Path('inputs/sft_processed/v7.1')
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

    original_count = len(data)
    print(f"   元のサンプル数: {original_count}")

    # フォーマット別にサンプルを分類
    format_samples = defaultdict(list)
    for i, sample in enumerate(data):
        fmt = get_format(sample)
        format_samples[fmt].append((i, sample))

    print("\n📊 フォーマット別の分布:")
    for fmt, samples in sorted(format_samples.items()):
        print(f"   {fmt}: {len(samples)} 件")

    # 新しいデータセットを構築
    new_data = list(data)  # 元データをコピー

    # ============================================================
    # 1. TOMLアップサンプリング（+100件のみ）
    # ============================================================
    print("\n🔧 1. TOMLアップサンプリング（+100件のみ）...")
    print(f"   目標追加数: {TOML_UPSAMPLE_COUNT} 件")

    toml_samples = format_samples.get('toml', [])
    print(f"   元のTOMLサンプル数: {len(toml_samples)} 件")

    toml_upsampled = select_toml_samples_for_upsample(toml_samples, TOML_UPSAMPLE_COUNT)

    print(f"   実際の追加数: +{len(toml_upsampled)} 件")
    new_data.extend(toml_upsampled)

    # ============================================================
    # 2. XMLエスケープ学習データ追加
    # ============================================================
    print("\n🔧 2. XMLエスケープ学習データ追加...")

    xml_escape_samples = create_xml_escape_samples()
    print(f"   XMLエスケープサンプル: +{len(xml_escape_samples)} 件")

    # 追加したサンプルの例を表示
    print("\n   追加したXMLエスケープサンプルの例:")
    for i, sample in enumerate(xml_escape_samples[:3]):
        escape_chars = sample['metadata'].get('escape_chars', [])
        print(f"   [{i+1}] スキーマ: {sample['metadata']['schema']}, エスケープ文字: {', '.join(escape_chars)}")

    new_data.extend(xml_escape_samples)

    # ============================================================
    # 3. Deep YAML アップサンプリング
    # ============================================================
    print("\n🔧 3. Deep YAML アップサンプリング...")

    yaml_samples = format_samples.get('yaml', [])
    deep_yaml = []

    for idx, sample in yaml_samples:
        assistant_content = sample['messages'][-1]['content']
        output_content = extract_output_content(assistant_content)
        depth = calculate_yaml_depth(output_content)

        if depth >= YAML_DEEP_THRESHOLD:
            deep_yaml.append((idx, sample, depth))

    print(f"   深いYAML (depth >= {YAML_DEEP_THRESHOLD}): {len(deep_yaml)} 件")

    yaml_upsampled = []
    for idx, sample, depth in deep_yaml:
        new_sample = copy.deepcopy(sample)
        yaml_upsampled.append(new_sample)  # 1つ追加で2倍

    print(f"   YAMLアップサンプリング: +{len(yaml_upsampled)} 件")
    new_data.extend(yaml_upsampled)

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
    print(f"   {'フォーマット':<10} {'v5':>6} {'v7.1':>6} {'増加':>6}")
    print("   " + "-" * 34)
    for fmt in ['toml', 'xml', 'yaml', 'json', 'csv']:
        original = len(format_samples.get(fmt, []))
        new = new_format_counts[fmt]
        diff = new - original
        print(f"   {fmt.upper():<10} {original:>6} {new:>6} +{diff:>5}")

    print("   " + "-" * 34)
    print(f"   {'合計':<10} {original_count:>6} {len(new_data):>6} +{len(new_data) - original_count:>5}")

    print("\n追加内容の内訳:")
    print(f"   TOMLアップサンプリング（複雑なもの優先）: +{len(toml_upsampled)}")
    print(f"   XMLエスケープ学習データ: +{len(xml_escape_samples)}")
    print(f"   深いYAML (depth>={YAML_DEEP_THRESHOLD}) アップサンプリング: +{len(yaml_upsampled)}")

    # 期待値との比較
    print("\n📋 期待値との比較:")
    expected = {
        'toml': (611, 711),
        'xml': (1012, 1020),
        'yaml': (624, 660),
        'json': (1075, 1075),
        'csv': (547, 547),
    }
    all_match = True
    for fmt, (exp_v5, exp_v71) in expected.items():
        actual_v5 = len(format_samples.get(fmt, []))
        actual_v71 = new_format_counts[fmt]
        v5_match = "✅" if actual_v5 == exp_v5 else f"❌ (期待: {exp_v5})"
        v71_match = "✅" if actual_v71 == exp_v71 else f"❌ (期待: {exp_v71})"
        print(f"   {fmt.upper()}: v5={actual_v5} {v5_match}, v7.1={actual_v71} {v71_match}")
        if actual_v5 != exp_v5 or actual_v71 != exp_v71:
            all_match = False

    expected_total_v71 = 4013
    actual_total_v71 = len(new_data)
    total_match = "✅" if actual_total_v71 == expected_total_v71 else f"❌ (期待: {expected_total_v71})"
    print(f"   合計: v7.1={actual_total_v71} {total_match}")

    # 出力
    print(f"\n💾 保存中: {output_path}")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(new_data, f, ensure_ascii=False, indent=2)

    print("\n✅ v7.1データセット作成完了!")
    print(f"   保存先: {output_path}")
    print(f"   サンプル数: {len(new_data)}")

    if all_match and actual_total_v71 == expected_total_v71:
        print("\n🎉 すべての期待値と一致しました！")
    else:
        print("\n⚠️ 一部の値が期待値と異なります。確認してください。")


if __name__ == '__main__':
    main()
