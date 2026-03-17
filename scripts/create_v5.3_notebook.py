#!/usr/bin/env python3
"""
v5.3ノートブック作成スクリプト
v5.2ノートブックをベースにv5.3用に修正
"""
import json
import re

# v5.2ノートブックを読み込み
with open('notebooks/SFT/メインコンペ(SFT)_v5.2.ipynb', 'r', encoding='utf-8') as f:
    notebook = json.load(f)

# セルを処理
for cell in notebook['cells']:
    if cell['cell_type'] == 'markdown':
        source = ''.join(cell['source']) if isinstance(cell['source'], list) else cell['source']

        # タイトルの変更
        source = source.replace('v5.2', 'v5.3')
        source = source.replace('ハイパラ調整版', 'ターゲットサンプル追加版')

        # データセット説明の更新
        source = source.replace('3,869件', '3,886件')
        source = source.replace('XMLエラー64件を除去', 'Empty Think Injection適用 + ターゲットサンプル17件追加')

        cell['source'] = [line + '\n' if i < len(source.split('\n'))-1 else line
                         for i, line in enumerate(source.split('\n'))]

    elif cell['cell_type'] == 'code':
        source = ''.join(cell['source']) if isinstance(cell['source'], list) else cell['source']

        # 環境変数の変更
        source = source.replace('v5.2', 'v5.3')
        source = source.replace('v5_train.json', 'v5.3_train.json')
        source = source.replace('_v5.2"', '_v5.3"')
        source = source.replace('改良データ (3,869件、XMLエラー除去済み)', 'v5.3データ (3,886件、Empty Think Injection + ターゲットサンプル17件)')

        # WandB設定の変更
        source = source.replace('v5.2_hyperparam_tuning', 'v5.3_targeted_samples')
        source = source.replace('"v5.2"', '"v5.3"')

        # ハイパーパラメータの変更（より保守的に）
        source = re.sub(r'os\.environ\["SFT_LR"\] = "[^"]*"', 'os.environ["SFT_LR"] = "3e-5"', source)
        source = re.sub(r'os\.environ\["SFT_LORA_R"\] = "[^"]*"', 'os.environ["SFT_LORA_R"] = "32"', source)
        source = re.sub(r'os\.environ\["SFT_LORA_ALPHA"\] = "[^"]*"', 'os.environ["SFT_LORA_ALPHA"] = "32"', source)

        cell['source'] = [line + '\n' if i < len(source.split('\n'))-1 else line
                         for i, line in enumerate(source.split('\n'))]

        # 出力をクリア
        if 'outputs' in cell:
            cell['outputs'] = []
        if 'execution_count' in cell:
            cell['execution_count'] = None

# v5.3ノートブックを保存
with open('notebooks/SFT/メインコンペ(SFT)_v5.3.ipynb', 'w', encoding='utf-8') as f:
    json.dump(notebook, f, ensure_ascii=False, indent=1)

print("✅ v5.3ノートブック作成完了: notebooks/SFT/メインコンペ(SFT)_v5.3.ipynb")

print("\n📝 主な変更点:")
print("  1. タイトル: v5.2 → v5.3")
print("  2. データセット: v5_train.json → v5.3_train.json (3,886件)")
print("  3. 出力ディレクトリ: _v5.2 → _v5.3")
print("  4. WandB名: v5.2_hyperparam_tuning → v5.3_targeted_samples")
print("  5. ハイパーパラメータ:")
print("     - LR: 5e-6 → 3e-5")
print("     - LORA_R: 64 → 32")
print("     - LORA_ALPHA: 128 → 32")
