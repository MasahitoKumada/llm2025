# v4 データ厳選戦略

## 背景

v3の失敗から、**データ量を増やす ≠ 精度向上** であることが判明。
むしろ、**少量でも質の高いデータ** が重要であると考えられる。

v4では「データ厳選」によるアプローチを採用する。

---

## 提案された厳選方法の分析

### 方法1: テストデータにない種類のデータを除外

**概要**: テストデータに出現しないタスクタイプを学習データから除外

**テストデータのタスク分布**:
```
Text to TOML: 25件 (16.7%)
CSV to JSON: 14件 (9.3%)
JSON to YAML: 14件 (9.3%)
XML to JSON: 13件 (8.7%)
TOML to JSON: 11件 (7.3%)
YAML to JSON: 10件 (6.7%)
... (全19種類)
```

**実装難易度**: ⭐ 簡単
**期待効果**: ⭐⭐ 中程度
**リスク**: 低い

**具体的なアクション**:
- 学習データのタスクタイプを抽出
- テストに存在しないタイプを除外
- 例: もし学習データに「JSON to TOML」があってテストにない場合は除外

**メリット**:
- 実装が簡単
- 明確な基準
- ノイズの少ない学習

**デメリット**:
- 除外対象が少ない可能性（ほとんどのタイプはカバーされている）

---

### 方法2: 定性的に質が悪いデータを除外

**概要**: 学習データを目視/ルールベースで確認し、質の悪いサンプルを除外

**質が悪いデータの例**:
- 説明文付きの出力（"Here's the JSON..."）
- マークダウンコードブロック付き（```json...```）
- 不完全な出力（途中で切れている）
- 明らかに間違った変換結果

**実装難易度**: ⭐⭐ 中程度
**期待効果**: ⭐⭐⭐ 高い
**リスク**: 中程度（v3で試したが悪化した経験あり）

**具体的なフィルタリングルール**:
```python
# 除外条件
BAD_PATTERNS = [
    r'```',           # マークダウン
    r"Here's",        # 説明文
    r"This is",       # 説明文
    r"Let me",        # 説明文
    r"Notes:",        # 注釈
]

# 追加条件: 出力が極端に短い/長い場合も除外
MIN_OUTPUT_LEN = 50
MAX_OUTPUT_LEN = 5000
```

**注意**: v3で品質フィルタリングを試みたがスコア低下した。
→ **フィルタリングは最小限に**、または別の方法と組み合わせる

---

### 方法3: テストデータの分布に近いデータを選択（次元圧縮）

**概要**: テストデータと学習データを埋め込みベクトル化し、分布が近いものを選択

**手法**:
1. テストデータのクエリを埋め込み（例: sentence-transformers）
2. 学習データのクエリを埋め込み
3. UMAP/t-SNEで次元圧縮
4. テストデータの分布の近くにある学習データを選択

**実装難易度**: ⭐⭐⭐ やや複雑
**期待効果**: ⭐⭐⭐ 高い
**リスク**: 中程度

**具体的なアプローチ**:
```python
from sentence_transformers import SentenceTransformer
import umap
import numpy as np

# 1. 埋め込み
model = SentenceTransformer('all-MiniLM-L6-v2')
test_embeddings = model.encode([t['query'] for t in test_data])
train_embeddings = model.encode([t['query'] for t in train_data])

# 2. 次元圧縮
reducer = umap.UMAP(n_components=2)
all_embeddings = np.vstack([test_embeddings, train_embeddings])
reduced = reducer.fit_transform(all_embeddings)

# 3. テスト分布の中心からの距離で選択
test_center = reduced[:len(test_data)].mean(axis=0)
distances = np.linalg.norm(reduced[len(test_data):] - test_center, axis=1)

# 4. 距離が近い上位N件を選択
top_indices = np.argsort(distances)[:2000]  # 上位2000件
```

**メリット**:
- テストデータに最も関連する学習データを選択できる
- 意味的な類似性を考慮

**デメリット**:
- 実装が複雑
- 埋め込みモデルの選択に依存
- 過度にテストに最適化するリスク

---

### 方法4: テストデータに近い学習データをベクトル検索

**概要**: 各テストデータに対して、最も類似した学習データをk件ずつ選択

**手法**:
1. テストデータのクエリを埋め込み
2. 学習データのクエリを埋め込み
3. 各テストクエリに対して、最近傍のk件を選択
4. 重複を除いて最終的な学習データセットを構築

**実装難易度**: ⭐⭐⭐ やや複雑
**期待効果**: ⭐⭐⭐⭐ 非常に高い
**リスク**: 低〜中程度

**具体的なアプローチ**:
```python
from sentence_transformers import SentenceTransformer
from sklearn.neighbors import NearestNeighbors

# 1. 埋め込み
model = SentenceTransformer('all-MiniLM-L6-v2')
test_embeddings = model.encode([t['query'] for t in test_data])
train_embeddings = model.encode([t['query'] for t in train_data])

# 2. k-NN検索
k = 20  # 各テストデータに対してk件の類似データ
nn = NearestNeighbors(n_neighbors=k, metric='cosine')
nn.fit(train_embeddings)
distances, indices = nn.kneighbors(test_embeddings)

# 3. 選択されたインデックスを取得（重複除去）
selected_indices = set(indices.flatten())
print(f"選択された学習データ: {len(selected_indices)}件")

# 4. 選択されたデータで学習データセットを構築
curated_train_data = [train_data[i] for i in selected_indices]
```

**メリット**:
- 各テストケースに対応する学習データを確保
- 無関係なデータを効率的に除外
- 実装が比較的シンプル

**デメリット**:
- kの値の調整が必要
- 過度にテストに最適化するリスク

---

## 推奨戦略

### v4では方法4（ベクトル検索）を採用

**理由**:
1. **直接的なアプローチ**: テストに類似したデータを選ぶという目的に最も適合
2. **データ量の制御が容易**: k値を調整することで最終データ量を制御可能
3. **実装がシンプル**: sentence-transformers + sklearn で実現可能
4. **リスクが低い**: 方法2のようにルールベースで除外するより安定

### 実装パラメータ案

```python
# 設定
EMBEDDING_MODEL = 'all-MiniLM-L6-v2'  # 軽量で高速
K_NEIGHBORS = 20  # 各テストに対して20件 → 最大3000件程度

# v2の成功データ量: 3,933件
# 目標データ量: 2,500〜3,500件（v2と同程度かやや少なめ）
```

### 補完的に方法1も併用

1. **まず方法4でベクトル検索**
2. **次に方法1でテストにないタイプを除外**
3. **最後に方法2で明らかな品質問題を除外**（最小限のみ）

---

## 実装ステップ

1. [ ] sentence-transformersでテスト/学習データの埋め込み生成
2. [ ] k-NN検索で類似データ選択
3. [ ] タスクタイプフィルタリング（方法1）
4. [ ] 最小限の品質フィルタリング（方法2）
5. [ ] 選択されたデータでv4データセット構築
6. [ ] 学習実行・評価

---

## 期待される効果

| バージョン | データ量 | スコア |
|-----------|---------|--------|
| v2 | 3,933件（フィルタなし） | 0.75074 |
| v3 | 8,541件（結合） | 0.72586 |
| **v4** | **2,500〜3,000件（厳選）** | **0.76〜0.78（目標）** |

「少量でも質の高いデータ」で、v2を超えるスコアを目指す。
