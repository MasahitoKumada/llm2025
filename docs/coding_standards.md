# コーディング規約

このプロジェクトで Python コードを書く際のルールをまとめます。

---

## ⚠️ 重要: Flake8 準拠

**すべての Python スクリプトは Flake8 のルールに準拠すること。**

### 主なルール

| ルール | 説明 | 例 |
|--------|------|-----|
| **E501** | 1行79文字以内 | 長い行は改行する |
| **F401** | 未使用のインポート禁止 | 使わないなら削除 |
| **E302** | 関数定義の前に2行空ける | |
| **E303** | 空行は2行まで | |
| **E722** | bare except 禁止 | `except Exception:` を使う |

### 行長制限への対応

```python
# ❌ NG: 79文字超過
result = some_function(arg1, arg2, arg3, arg4, arg5, arg6, very_long_argument_name)

# ✅ OK: 改行して対応
result = some_function(
    arg1, arg2, arg3, arg4, arg5, arg6,
    very_long_argument_name
)

# ✅ OK: 中間変数を使う
very_long_list = [
    item for item in data
    if item['value'] > 0 and item['status'] == 'active'
]
result = process_items(very_long_list)

# ✅ OK: 辞書内包表記の分割
issues_count = {
    k: len(v) for k, v in issues.items()
}
```

### f-string のルール

```python
# ❌ NG: プレースホルダなしの f-string
print(f"固定文字列")

# ✅ OK: 通常の文字列
print("固定文字列")

# ✅ OK: プレースホルダあり
print(f"値: {value}")
```

### 例外処理

```python
# ❌ NG: bare except
try:
    data = json.loads(text)
except:
    return None

# ✅ OK: 具体的な例外を指定
try:
    data = json.loads(text)
except json.JSONDecodeError:
    return None
```

---

## コード作成時のチェックリスト

Python スクリプトを作成・修正する際は、以下を確認すること：

- [ ] 1行79文字以内に収まっているか
- [ ] 未使用のインポートがないか
- [ ] bare except を使っていないか
- [ ] f-string にプレースホルダがあるか
- [ ] 関数定義の前に2行空けているか

---

## VS Code 設定

VS Code で Flake8 を有効にするには `.vscode/settings.json` に以下を追加：

```json
{
  "python.linting.enabled": true,
  "python.linting.flake8Enabled": true,
  "python.linting.flake8Args": [
    "--max-line-length=79"
  ]
}
```

---

## その他のルール

### ファイル構造

```
scripts/           # 分析・ユーティリティスクリプト
docs/              # ドキュメント
plans/             # 戦略・計画書
inputs/            # 入力データ
outputs/           # 出力データ
```

### 命名規則

- **変数・関数**: `snake_case`
- **クラス**: `PascalCase`
- **定数**: `UPPER_SNAKE_CASE`
- **ファイル名**: `snake_case.py`

### ドキュメント

- すべての関数に docstring を書く
- スクリプト冒頭に説明コメントを書く

```python
#!/usr/bin/env python3
"""
スクリプトの説明

詳細な説明をここに書く。
"""
```

---

## 参考リンク

- [Flake8 公式ドキュメント](https://flake8.pycqa.org/)
- [PEP 8 スタイルガイド](https://peps.python.org/pep-0008/)
