#!/usr/bin/env python3
"""
ローカル簡易評価スクリプト

推論結果のフォーマット妥当性を検証し、簡易スコアを算出する。
実際のスコアとはずれる可能性があるが、フォーマットエラーの早期発見に有用。

使用方法:
    python scripts/local_evaluation.py

必要なパッケージ:
    pip install pyyaml toml pandas
"""
import json
import re
import pandas as pd
from collections import defaultdict
from pathlib import Path
import yaml
import toml
import xml.etree.ElementTree as ET
import io

# パス設定
BASE_DIR = Path(__file__).parent.parent
PUBLIC_FILE = BASE_DIR / "test_data" / "public_150.json"
OUTPUTS_DIR = BASE_DIR / "outputs"


def strip_code_fence(text):
    """コードフェンスを除去（LB評価との整合性向上）"""
    text = text.strip()
    # ```json, ```yaml, ```toml, ```xml, ```csv などを除去
    pattern = r'^```\w*\n?(.*?)```$'
    match = re.match(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    # 開始タグのみの場合（閉じタグなし）
    if text.startswith('```'):
        lines = text.split('\n')
        if lines[0].startswith('```'):
            return '\n'.join(lines[1:]).strip()
    return text


def validate_format(text, fmt, strip_fence=True):
    """フォーマットの妥当性を検証"""
    if strip_fence:
        text = strip_code_fence(text)
    try:
        if fmt == 'JSON':
            json.loads(text)
        elif fmt == 'YAML':
            yaml.safe_load(text)
        elif fmt == 'TOML':
            toml.loads(text)
        elif fmt == 'XML':
            ET.fromstring(text)
        elif fmt == 'CSV':
            if not text.strip():
                raise ValueError("Empty CSV")
            pd.read_csv(io.StringIO(text))
        else:
            return False, f"Unknown format: {fmt}"
        return True, None
    except Exception as e:
        return False, str(e)


def evaluate_inference(public_file, inference_file, version_name=""):
    """推論結果を評価"""

    # 正解データ読み込み
    with open(public_file, 'r', encoding='utf-8') as f:
        ground_truth = json.load(f)

    # task_id -> output_type の辞書を作成
    id_to_type = {}
    for entry in ground_truth:
        tid = str(entry.get('task_id'))
        otype = entry.get('output_type')
        if tid and otype:
            id_to_type[tid] = otype.upper()

    # 推論結果読み込み
    with open(inference_file, 'r', encoding='utf-8') as f:
        inferences = json.load(f)

    # 集計用
    stats = defaultdict(lambda: {"total": 0, "valid": 0})
    errors = []

    for item in inferences:
        tid = str(item.get('task_id'))
        generated_text = item.get('generation', '')

        target_fmt = id_to_type.get(tid)

        if not target_fmt:
            continue

        is_valid, error_msg = validate_format(generated_text, target_fmt)

        stats[target_fmt]["total"] += 1
        if is_valid:
            stats[target_fmt]["valid"] += 1
        else:
            errors.append({
                "task_id": tid,
                "format": target_fmt,
                "error": error_msg,
                "generated_snippet": generated_text[:100]
            })

    # 結果を計算
    total_valid = sum(data["valid"] for data in stats.values())
    total_count = sum(data["total"] for data in stats.values())
    overall_rate = (total_valid / total_count) * 100 if total_count > 0 else 0

    return {
        "version": version_name,
        "overall_rate": overall_rate,
        "total_valid": total_valid,
        "total_count": total_count,
        "stats": dict(stats),
        "error_count": len(errors),
        "errors": errors
    }


def main():
    """メイン処理: 全バージョンを評価"""

    print("=" * 70)
    print("🔍 ローカル簡易評価 - 全バージョン比較（コードフェンス除去版）")
    print("=" * 70)

    # 評価対象のバージョン
    versions = ['v0', 'v1', 'v2', 'v3', 'v4', 'v4.1', 'v5', 'v5.1', 'v5.2']

    # 実際のスコア（提出結果）
    actual_scores = {
        'v0': 0.69426,
        'v1': 0.59555,
        'v2': 0.75074,
        'v3': 0.72586,
        'v4': 0.74649,
        'v4.1': 0.73439,
        'v5': 0.73981,
        'v5.1': 0.724871,
        'v5.2': 0.777023
    }

    results = []

    for version in versions:
        inference_file = OUTPUTS_DIR / f"inference_{version}.json"

        if not inference_file.exists():
            print(f"⚠️ {version}: ファイルなし")
            continue

        result = evaluate_inference(PUBLIC_FILE, inference_file, version)
        results.append(result)

    # サマリー表示
    print("\n" + "=" * 70)
    print("📊 評価結果サマリー")
    print("=" * 70)
    header = f"{'Ver':<6} {'簡易':>8} {'LB':>8} {'差':>7} {'OK':>5} {'NG':>5}"
    print(header)
    print("-" * 70)

    for result in results:
        version = result["version"]
        local_score = result["overall_rate"]
        actual_score = actual_scores.get(version, 0) * 100
        diff = local_score - actual_score

        row = f"{version:<6} {local_score:>7.1f}% {actual_score:>7.1f}% "
        row += f"{diff:>+6.1f}% {result['total_valid']:>5} {result['error_count']:>5}"
        print(row)

    # フォーマット別詳細
    print("\n" + "=" * 70)
    print("📋 フォーマット別成功率")
    print("=" * 70)

    formats = ['JSON', 'YAML', 'TOML', 'XML', 'CSV']

    # ヘッダー
    header = f"{'Ver':<6}"
    for fmt in formats:
        header += f" {fmt:>7}"
    print(header)
    print("-" * 70)

    for result in results:
        row = f"{result['version']:<6}"
        for fmt in formats:
            if fmt in result['stats']:
                data = result['stats'][fmt]
                rate = (data['valid'] / data['total']) * 100
                row += f" {rate:>6.0f}%"
            else:
                row += f" {'N/A':>7}"
        print(row)

    # 最新バージョンのエラー詳細
    if results:
        latest = results[-1]
        if latest['errors']:
            print(f"\n⚠️ {latest['version']} のエラー詳細（最初の5件）:")
            for err in latest['errors'][:5]:
                err_msg = err['error'][:40].replace('\n', ' ')
                print(f"  [{err['format']}] {err['task_id']}: {err_msg}...")

    print("\n" + "=" * 70)
    print("✅ 評価完了（コードフェンス自動除去済み）")
    print("=" * 70)


if __name__ == "__main__":
    main()
