#!/usr/bin/env python3
"""
データセット厳選スクリプト

テストデータに類似した学習データをベクトル検索で選択し、
高品質なデータセットを構築する。

使用方法:
    python scripts/curate_dataset.py

依存関係:
    pip install sentence-transformers scikit-learn numpy

出力:
    inputs/sft_processed/v*/train.json
"""
import json
import re
from pathlib import Path
from collections import Counter
from sentence_transformers import SentenceTransformer
from sklearn.neighbors import NearestNeighbors


# パス設定
BASE_DIR = Path(__file__).parent.parent
TEST_DATA_PATH = BASE_DIR / "test_data" / "public_150.json"
SFT_DIR = BASE_DIR / "inputs" / "sft"
OUTPUT_DIR = BASE_DIR / "inputs" / "sft_processed" / "v4.1"

# 設定
EMBEDDING_MODEL = 'all-MiniLM-L6-v2'  # 軽量で高速
K_NEIGHBORS = 50  # 各テストに対して選択する学習データ数（v4: 100 → v4.1: 50）
MIN_OUTPUT_LEN = 30  # 出力の最小長
MAX_OUTPUT_LEN = 8000  # 出力の最大長

# 品質フィルタリング用パターン（最小限）
BAD_PATTERNS = [
    r'^Here\'s',
    r'^This is the',
    r'^Let me',
    r'^Below is',
    r'Notes:',
]


def load_json(path):
    """JSONファイルを読込む"""
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(data, path):
    """JSONファイルを保存する"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"保存: {path} ({len(data)}件)")


def extract_query(item):
    """
    学習データからクエリを抽出する。
    データセットによって形式が異なるため、複数のパターンに対応。
    """
    # messages形式
    if 'messages' in item:
        for msg in item['messages']:
            if msg.get('role') == 'user':
                return msg.get('content', '')

    # query形式（テストデータ）
    if 'query' in item:
        return item['query']

    return ''


def extract_output(item):
    """学習データから出力を抽出する"""
    if 'messages' in item:
        for msg in item['messages']:
            if msg.get('role') == 'assistant':
                return msg.get('content', '')
    return ''


def extract_task_type(item):
    """タスクタイプを抽出する"""
    # テストデータ形式
    if 'task_name' in item:
        return item['task_name']

    # 学習データ形式（subcategory）
    if 'subcategory' in item:
        return item['subcategory']

    # メタデータから
    if 'metadata' in item:
        meta = item['metadata']
        fmt = meta.get('format', '')
        task_type = meta.get('type', '')
        if fmt and task_type:
            return f"{task_type}_{fmt}"

    return 'unknown'


def check_quality(item):
    """品質チェック（問題があればFalseを返す）"""
    output = extract_output(item)

    # 出力長チェック
    if len(output) < MIN_OUTPUT_LEN:
        return False, 'too_short'
    if len(output) > MAX_OUTPUT_LEN:
        return False, 'too_long'

    # パターンチェック（最小限）
    for pattern in BAD_PATTERNS:
        if re.search(pattern, output, re.IGNORECASE):
            return False, 'bad_pattern'

    return True, 'ok'


def load_all_sft_data():
    """全SFTデータセットを読込む"""
    all_data = []

    for dataset_dir in sorted(SFT_DIR.iterdir()):
        if not dataset_dir.is_dir():
            continue

        # v3やprocessedフォルダは除外
        if 'processed' in dataset_dir.name:
            continue

        train_json = dataset_dir / "train.json"
        if not train_json.exists():
            continue

        data = load_json(train_json)
        print(f"読み込み: {dataset_dir.name} ({len(data)}件)")

        for item in data:
            item['_source'] = dataset_dir.name
            all_data.append(item)

    print(f"合計: {len(all_data)}件")
    return all_data


def get_test_task_types(test_data):
    """テストデータのタスクタイプを取得"""
    types = set()
    for item in test_data:
        task_name = item.get('task_name', '')
        if task_name:
            types.add(task_name)
    return types


def filter_by_task_type(data, valid_types):
    """テストに存在するタスクタイプのみを残す"""
    filtered = []
    removed_types = Counter()

    # タスクタイプのマッピング（学習データ形式→テスト形式）
    type_mapping = {
        'text_to_json': 'Text to JSON',
        'text_to_yaml': 'Text to YAML',
        'text_to_toml': 'Text to TOML',
        'text_to_xml': 'Text to XML',
        'text_to_csv': 'Text to CSV',
        'csv_to_json': 'CSV to JSON',
        'csv_to_yaml': 'CSV to YAML',
        'csv_to_xml': 'CSV to XML',
        'json_to_yaml': 'JSON to YAML',
        'json_to_xml': 'JSON to XML',
        'json_to_csv': 'JSON to CSV',
        'yaml_to_json': 'YAML to JSON',
        'yaml_to_xml': 'YAML to XML',
        'yaml_to_csv': 'YAML to CSV',
        'xml_to_json': 'XML to JSON',
        'xml_to_yaml': 'XML to YAML',
        'xml_to_csv': 'XML to CSV',
        'toml_to_json': 'TOML to JSON',
        'toml_to_yaml': 'TOML to YAML',
    }

    # 逆マッピング（テスト形式→学習データ形式）
    valid_types_lower = set()
    for t in valid_types:
        valid_types_lower.add(t.lower().replace(' ', '_'))
        # 元の形式も追加
        valid_types_lower.add(t)

    for item in data:
        task_type = extract_task_type(item)
        normalized = task_type.lower().replace(' ', '_')

        # マッピングを使って正規化
        mapped = type_mapping.get(normalized, task_type)

        if mapped in valid_types or normalized in valid_types_lower:
            filtered.append(item)
        else:
            removed_types[task_type] += 1

    print(f"タスクタイプフィルタ: {len(data)} → {len(filtered)}件")
    if removed_types:
        print("除外されたタイプ:", dict(removed_types.most_common(10)))

    return filtered


def filter_by_quality(data):
    """品質フィルタリング"""
    filtered = []
    removed_reasons = Counter()

    for item in data:
        ok, reason = check_quality(item)
        if ok:
            filtered.append(item)
        else:
            removed_reasons[reason] += 1

    print(f"品質フィルタ: {len(data)} → {len(filtered)}件")
    if removed_reasons:
        print("除外理由:", dict(removed_reasons))

    return filtered


def select_by_similarity(test_data, train_data, k=K_NEIGHBORS):
    """ベクトル検索で類似データを選択"""
    print(f"\n埋め込みモデル: {EMBEDDING_MODEL}")
    print("埋め込み生成中...")

    model = SentenceTransformer(EMBEDDING_MODEL)

    # クエリを抽出
    test_queries = [item.get('query', '') for item in test_data]
    train_queries = [extract_query(item) for item in train_data]

    # 埋め込み生成
    print(f"テストデータ: {len(test_queries)}件")
    test_emb = model.encode(test_queries, show_progress_bar=True)

    print(f"学習データ: {len(train_queries)}件")
    train_emb = model.encode(train_queries, show_progress_bar=True)

    # k-NN検索
    print(f"\nk-NN検索 (k={k})...")
    nn = NearestNeighbors(n_neighbors=min(k, len(train_data)), metric='cosine')
    nn.fit(train_emb)
    distances, indices = nn.kneighbors(test_emb)

    # 選択されたインデックスを取得（重複除去）
    selected_indices = set(indices.flatten())
    print(f"選択された学習データ: {len(selected_indices)}件")

    # 選択されたデータを返す
    return [train_data[i] for i in sorted(selected_indices)]


def analyze_curated_data(data, test_data):
    """厳選されたデータを分析"""
    print("\n" + "=" * 60)
    print("📊 厳選データの分析")
    print("=" * 60)

    print(f"\n総件数: {len(data)}")

    # ソース別
    sources = Counter(item.get('_source', 'unknown') for item in data)
    print("\nソース別:")
    for source, count in sources.most_common():
        print(f"  {source}: {count}件")

    # タスクタイプ別
    types = Counter(extract_task_type(item) for item in data)
    print("\nタスクタイプ別 (上位10):")
    for task_type, count in types.most_common(10):
        print(f"  {task_type}: {count}件")

    # テストデータとの比較
    test_types = Counter(item.get('task_name', '') for item in test_data)
    print("\nテストデータのタスクタイプ (上位10):")
    for task_type, count in test_types.most_common(10):
        print(f"  {task_type}: {count}件")


def main():
    print("=" * 60)
    print("データセット厳選スクリプト")
    print("=" * 60)

    # テストデータ読み込み
    print("\n1. テストデータ読み込み")
    test_data = load_json(TEST_DATA_PATH)
    print(f"テストデータ: {len(test_data)}件")

    test_task_types = get_test_task_types(test_data)
    print(f"テストのタスクタイプ: {len(test_task_types)}種類")

    # 全SFTデータ読み込み
    print("\n2. SFTデータ読み込み")
    all_data = load_all_sft_data()

    # タスクタイプフィルタリング
    print("\n3. タスクタイプフィルタリング")
    filtered_data = filter_by_task_type(all_data, test_task_types)

    # 品質フィルタリング
    print("\n4. 品質フィルタリング")
    quality_data = filter_by_quality(filtered_data)

    # ベクトル検索で類似データ選択
    print("\n5. ベクトル検索による類似データ選択")
    curated_data = select_by_similarity(test_data, quality_data, k=K_NEIGHBORS)

    # 分析
    analyze_curated_data(curated_data, test_data)

    # 保存
    print("\n6. データセット保存")
    output_path = OUTPUT_DIR / "train.json"
    save_json(curated_data, output_path)

    print("\n" + "=" * 60)
    print("✅ 完了!")
    print(f"出力: {output_path}")
    print(f"件数: {len(curated_data)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
