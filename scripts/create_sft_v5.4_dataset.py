#!/usr/bin/env python3
"""
SFT v5.4 データセット作成スクリプト

v11戦略に基づいて、高品質800件のデータセットを作成します。

戦略の要点:
1. TOMLを明示的に学習しない（他フォーマットからの転移学習で達成可能）
2. 高品質800件データで学習
3. Empty Think Injection適用（Qwen3のtool_call回避）

フォーマット配分:
- JSON: 200件（基盤フォーマット）
- YAML: 250件（TOML転移学習のソース、重要）
- CSV: 150件（シンプル構造）
- XML: 150件（重点改善対象）
- TOML: 50件（最小限、転移学習依存）

選定基準:
1. パース可能なデータのみ（各フォーマットの構文検証）
2. CoT（Approach/Output）を含まないクリーンな出力
3. 適切な長さ（極端に短い/長いものを除外）
4. 多様な構造深度（浅い～深いをバランスよく）

入力: inputs/sft_processed/v5/train.json (3,869件)
出力: inputs/sft_processed/v5.4/train.json (約800件)
"""
import json
import re
import csv
import io
import random
from pathlib import Path
from typing import Optional, Tuple, Dict, List
from collections import defaultdict

# フォーマット別目標件数
FORMAT_TARGETS = {
    'json': 200,
    'yaml': 250,  # TOML転移学習ソース（重要）
    'csv': 150,
    'xml': 150,
    'toml': 50,   # 最小限
}

# 長さの閾値
MIN_OUTPUT_LENGTH = 50   # 最小出力長
MAX_OUTPUT_LENGTH = 3000 # 最大出力長


def detect_format(content: str) -> Optional[str]:
    """
    コンテンツからフォーマットを検出します。

    Args:
        content: 構造化データのコンテンツ

    Returns:
        検出されたフォーマット名、または None
    """
    content_stripped = content.strip()

    # JSON検出: { または [ で始まる
    if content_stripped.startswith('{') or content_stripped.startswith('['):
        return 'json'

    # XML検出: < で始まる（<?xml または <root など）
    if content_stripped.startswith('<'):
        return 'xml'

    # CSV検出: カンマ区切りの行構造
    lines = content_stripped.split('\n')
    if len(lines) >= 2:
        first_line = lines[0]
        if ',' in first_line and not first_line.startswith('-') and not ':' in first_line.split(',')[0]:
            # ヘッダー行っぽい場合
            return 'csv'

    # TOML検出: [section] または key = value パターン
    if re.search(r'^\[[\w.-]+\]', content_stripped, re.MULTILINE):
        return 'toml'
    if re.search(r'^[\w_]+ = ', content_stripped, re.MULTILINE):
        # YAMLとの区別: = を使う（YAMLは:を使う）
        if ' = ' in content_stripped and ': ' not in content_stripped.split('\n')[0]:
            return 'toml'

    # YAML検出: key: value パターン
    if re.search(r'^[\w_-]+:\s', content_stripped, re.MULTILINE):
        return 'yaml'
    if content_stripped.startswith('- '):
        return 'yaml'

    return None


def validate_json(content: str) -> bool:
    """JSONの構文検証"""
    try:
        json.loads(content)
        return True
    except (json.JSONDecodeError, ValueError):
        return False


def validate_yaml(content: str) -> bool:
    """YAMLの構文検証（簡易版）"""
    try:
        import yaml
        yaml.safe_load(content)
        return True
    except:
        # yamlモジュールがない場合は基本的なチェック
        lines = content.strip().split('\n')
        if len(lines) == 0:
            return False
        # 基本的なYAML構造チェック
        for line in lines:
            if line.strip() and not line.startswith('#'):
                # キー: 値 または - item 形式
                if ':' in line or line.strip().startswith('-'):
                    return True
        return len(lines) > 0


def validate_csv(content: str) -> bool:
    """CSVの構文検証"""
    try:
        reader = csv.reader(io.StringIO(content))
        rows = list(reader)
        if len(rows) < 2:  # ヘッダー + 少なくとも1行のデータ
            return False
        header_cols = len(rows[0])
        # 全行が同じ列数か確認（許容範囲あり）
        for row in rows[1:]:
            if abs(len(row) - header_cols) > 2:  # 2列以上の差は許容しない
                return False
        return True
    except csv.Error:
        return False


def validate_xml(content: str) -> bool:
    """XMLの構文検証"""
    try:
        import xml.etree.ElementTree as ET
        # XML宣言がない場合は追加
        if not content.strip().startswith('<?xml'):
            content_to_parse = content
        else:
            content_to_parse = content
        ET.fromstring(content_to_parse)
        return True
    except ET.ParseError:
        # 複数のルート要素がある場合、ラッパーを追加して再試行
        try:
            wrapped = f"<root>{content}</root>"
            import xml.etree.ElementTree as ET
            ET.fromstring(wrapped)
            return True
        except:
            return False
    except Exception:
        return False


def validate_toml(content: str) -> bool:
    """TOMLの構文検証（簡易版）"""
    try:
        import tomllib
        tomllib.loads(content)
        return True
    except:
        # tomllibがない場合は基本的なチェック
        lines = content.strip().split('\n')
        has_valid_structure = False
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            # セクション [name] または キー = 値
            if re.match(r'^\[[\w.-]+\]$', line):
                has_valid_structure = True
            elif re.match(r'^[\w_-]+ = .+$', line):
                has_valid_structure = True
            elif re.match(r'^\[\[[\w.-]+\]\]$', line):
                has_valid_structure = True
        return has_valid_structure


def validate_format(content: str, format_type: str) -> bool:
    """フォーマットに応じた構文検証"""
    validators = {
        'json': validate_json,
        'yaml': validate_yaml,
        'csv': validate_csv,
        'xml': validate_xml,
        'toml': validate_toml,
    }

    validator = validators.get(format_type)
    if validator:
        return validator(content)
    return False


def extract_pure_output(content: str) -> str:
    """
    assistant回答から純粋な構造化データ部分のみを抽出します。
    """
    # Step 1: "Output:" 以降の部分を抽出
    output_patterns = [
        r'Output:\s*\n',
        r'OUTPUT:\s*\n',
        r'Final:\s*\n',
        r'Answer:\s*\n',
        r'Result:\s*\n',
        r'Response:\s*\n',
    ]

    result = content

    for pattern in output_patterns:
        match = re.search(pattern, result, re.IGNORECASE)
        if match:
            result = result[match.end():]
            break

    # Step 2: マークダウンコードブロックの除去
    code_block_pattern = r'^```\w*\s*\n?(.*?)```\s*$'
    code_block_match = re.match(code_block_pattern, result.strip(), re.DOTALL)
    if code_block_match:
        result = code_block_match.group(1)

    result = result.strip()

    # Step 3: 説明文プレフィックスの除去
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
    """Empty Think Injection を適用"""
    return f"<think>\n</think>\n\n{content}"


def has_cot_markers(content: str) -> bool:
    """CoT（Chain of Thought）マーカーが含まれているか確認"""
    cot_patterns = [
        r'Approach:',
        r'Step \d+:',
        r'First,',
        r'Let me',
        r'I will',
        r'Let\'s',
    ]
    for pattern in cot_patterns:
        if re.search(pattern, content, re.IGNORECASE):
            return True
    return False


def estimate_depth(content: str, format_type: str) -> int:
    """構造の深度を推定"""
    if format_type == 'json':
        try:
            data = json.loads(content)
            return _get_dict_depth(data)
        except:
            return 1
    elif format_type == 'yaml':
        # インデントベースで推定
        max_indent = 0
        for line in content.split('\n'):
            if line.strip():
                indent = len(line) - len(line.lstrip())
                max_indent = max(max_indent, indent // 2)
        return max_indent + 1
    elif format_type == 'xml':
        # タグのネスト深度で推定
        depth = 0
        max_depth = 0
        for char in content:
            if char == '<':
                depth += 1
                max_depth = max(max_depth, depth)
            elif char == '>':
                depth = max(0, depth - 1)
        return max_depth // 2 + 1
    elif format_type == 'toml':
        # セクション数で推定
        sections = re.findall(r'^\[+[\w.-]+\]+', content, re.MULTILINE)
        return min(len(sections) + 1, 5)
    elif format_type == 'csv':
        # 行数で推定（深度というより複雑さ）
        return min(len(content.split('\n')) // 3, 3) + 1
    return 1


def _get_dict_depth(obj, current_depth=1) -> int:
    """辞書/リストの深度を計算"""
    if isinstance(obj, dict):
        if not obj:
            return current_depth
        return max(_get_dict_depth(v, current_depth + 1) for v in obj.values())
    elif isinstance(obj, list):
        if not obj:
            return current_depth
        return max(_get_dict_depth(item, current_depth + 1) for item in obj)
    return current_depth


def process_sample(sample: dict) -> Optional[Tuple[dict, str, int]]:
    """
    サンプルを処理し、品質基準を満たすかチェックします。

    Returns:
        (処理済みサンプル, フォーマット, 深度) または None
    """
    messages = sample.get('messages', [])
    if len(messages) < 3:
        return None

    assistant_msg = messages[-1]
    if assistant_msg.get('role') != 'assistant':
        return None

    original_content = assistant_msg['content']

    # 純粋な出力を抽出
    pure_output = extract_pure_output(original_content)

    # 長さチェック
    if len(pure_output) < MIN_OUTPUT_LENGTH or len(pure_output) > MAX_OUTPUT_LENGTH:
        return None

    # CoTマーカーが残っていないか確認
    if has_cot_markers(pure_output):
        return None

    # フォーマット検出
    format_type = detect_format(pure_output)
    if format_type is None:
        # メタデータからフォーマットを取得
        metadata = sample.get('metadata', {})
        format_type = metadata.get('format')

    if format_type is None:
        return None

    # フォーマット検証
    if not validate_format(pure_output, format_type):
        return None

    # 深度推定
    depth = estimate_depth(pure_output, format_type)

    # 新しいサンプルを作成
    new_sample = sample.copy()
    new_messages = []

    for msg in messages:
        new_msg = msg.copy()
        if msg.get('role') == 'assistant':
            # Empty Think Injection適用
            new_msg['content'] = apply_empty_think_injection(pure_output)
        new_messages.append(new_msg)

    new_sample['messages'] = new_messages

    # メタデータ更新
    if 'metadata' not in new_sample:
        new_sample['metadata'] = {}
    new_sample['metadata']['format'] = format_type
    new_sample['metadata']['depth'] = depth
    new_sample['metadata']['v5.4_processed'] = True

    return (new_sample, format_type, depth)


def select_diverse_samples(
    candidates: List[Tuple[dict, str, int]],
    target_count: int
) -> List[dict]:
    """
    深度の多様性を考慮してサンプルを選択します。
    """
    if len(candidates) <= target_count:
        return [c[0] for c in candidates]

    # 深度でグループ化
    by_depth = defaultdict(list)
    for sample, fmt, depth in candidates:
        by_depth[depth].append(sample)

    # 各深度から均等に選択
    selected = []
    depths = sorted(by_depth.keys())
    per_depth = target_count // len(depths) if depths else target_count
    remainder = target_count % len(depths) if depths else 0

    for i, depth in enumerate(depths):
        count = per_depth + (1 if i < remainder else 0)
        samples = by_depth[depth]
        random.shuffle(samples)
        selected.extend(samples[:count])

    # 足りない場合はランダムに追加
    if len(selected) < target_count:
        all_samples = [c[0] for c in candidates if c[0] not in selected]
        random.shuffle(all_samples)
        selected.extend(all_samples[:target_count - len(selected)])

    return selected[:target_count]


def main():
    """メイン処理"""
    random.seed(42)  # 再現性のためのシード

    # パス設定
    input_path = Path('inputs/sft_processed/v5/train.json')
    output_dir = Path('inputs/sft_processed/v5.4')
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

    print(f"   ソースサンプル数: {len(data)}")
    print(f"\n🎯 目標構成:")
    for fmt, count in FORMAT_TARGETS.items():
        print(f"   {fmt.upper()}: {count}件")
    print(f"   合計: {sum(FORMAT_TARGETS.values())}件")

    # 各サンプルを処理してフォーマット別に分類
    print("\n🔄 サンプル処理中...")
    candidates_by_format: Dict[str, List[Tuple[dict, str, int]]] = defaultdict(list)

    stats = {
        'total': len(data),
        'processed': 0,
        'invalid_length': 0,
        'has_cot': 0,
        'unknown_format': 0,
        'parse_error': 0,
    }

    for i, sample in enumerate(data):
        result = process_sample(sample)

        if result is None:
            # エラー種別のカウント（詳細）
            messages = sample.get('messages', [])
            if len(messages) >= 3:
                content = messages[-1].get('content', '')
                pure = extract_pure_output(content)
                if len(pure) < MIN_OUTPUT_LENGTH or len(pure) > MAX_OUTPUT_LENGTH:
                    stats['invalid_length'] += 1
                elif has_cot_markers(pure):
                    stats['has_cot'] += 1
                elif detect_format(pure) is None:
                    stats['unknown_format'] += 1
                else:
                    stats['parse_error'] += 1
            continue

        processed_sample, format_type, depth = result
        candidates_by_format[format_type].append(result)
        stats['processed'] += 1

        # 進捗表示
        if (i + 1) % 1000 == 0:
            print(f"   処理済み: {i + 1} / {len(data)}")

    # 統計表示
    print(f"\n📊 処理結果:")
    print(f"   有効サンプル: {stats['processed']} / {stats['total']}")
    print(f"   除外（長さ不正）: {stats['invalid_length']}")
    print(f"   除外（CoT残存）: {stats['has_cot']}")
    print(f"   除外（フォーマット不明）: {stats['unknown_format']}")
    print(f"   除外（パースエラー）: {stats['parse_error']}")

    print(f"\n📋 フォーマット別候補数:")
    for fmt in FORMAT_TARGETS.keys():
        count = len(candidates_by_format[fmt])
        target = FORMAT_TARGETS[fmt]
        status = "✅" if count >= target else "⚠️"
        print(f"   {fmt.upper()}: {count}件 (目標: {target}件) {status}")

    # 各フォーマットから目標数を選択
    print("\n🎲 多様性を考慮してサンプル選択中...")
    final_dataset = []

    for fmt, target_count in FORMAT_TARGETS.items():
        candidates = candidates_by_format[fmt]
        selected = select_diverse_samples(candidates, target_count)
        final_dataset.extend(selected)

        # 深度分布の確認
        depths = [s['metadata']['depth'] for s in selected]
        depth_dist = defaultdict(int)
        for d in depths:
            depth_dist[d] += 1
        print(f"   {fmt.upper()}: {len(selected)}件選択 (深度分布: {dict(sorted(depth_dist.items()))})")

    # シャッフル
    random.shuffle(final_dataset)

    # 出力
    print(f"\n💾 保存中: {output_path}")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(final_dataset, f, ensure_ascii=False, indent=2)

    # 最終統計
    print(f"\n✅ データセット作成完了!")
    print(f"   出力件数: {len(final_dataset)}")
    print(f"   保存先: {output_path}")

    # フォーマット別内訳
    format_counts = defaultdict(int)
    for sample in final_dataset:
        fmt = sample.get('metadata', {}).get('format', 'unknown')
        format_counts[fmt] += 1

    print(f"\n📊 最終フォーマット別内訳:")
    for fmt in ['json', 'yaml', 'csv', 'xml', 'toml']:
        count = format_counts[fmt]
        target = FORMAT_TARGETS.get(fmt, 0)
        pct = count / len(final_dataset) * 100 if final_dataset else 0
        print(f"   {fmt.upper()}: {count}件 ({pct:.1f}%) [目標: {target}件]")

    # Empty Think Injection確認
    think_prefix = "<think>\n</think>\n\n"
    has_think = sum(1 for s in final_dataset
                   if s['messages'][-1]['content'].startswith(think_prefix))
    print(f"\n🧠 Empty Think Injection適用数: {has_think} / {len(final_dataset)}")

    # サンプル表示
    print("\n📝 サンプル出力（最初の1件）:")
    print("-" * 60)
    if final_dataset:
        sample = final_dataset[0]
        print(f"フォーマット: {sample.get('metadata', {}).get('format', 'unknown')}")
        print(f"深度: {sample.get('metadata', {}).get('depth', 'unknown')}")
        content = sample['messages'][-1]['content']
        print(f"出力（最初の300文字）:\n{content[:300]}...")
    print("-" * 60)


if __name__ == '__main__':
    main()
