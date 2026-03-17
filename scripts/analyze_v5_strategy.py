#!/usr/bin/env python3
"""
v5戦略分析スクリプト
テストデータ（public_150.json）と推論結果（v0, v1, v2）を分析し、
データ増減戦略を検討する
"""

import json
import os
from collections import Counter, defaultdict
from typing import Dict, List, Any, Tuple


# ========== 設定 ==========
TEST_DATA_PATH = "test_data/public_150.json"
INFERENCE_PATHS = {
    "v0": "outputs/inference_v0.json",
    "v1": "outputs/inference_v1.json",
    "v2": "outputs/inference_v2.json",
}
SFT_DATA_PATH = "inputs/sft/1-1_512_v2/train.json"  # v2で使用したベースデータ
SCORES = {"v0": 0.69426, "v1": 0.59555, "v2": 0.75074}


# ========== ユーティリティ関数 ==========
def load_json(path: str) -> Any:
    """JSONファイルを読込む"""
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def detect_format_from_content(content: str) -> str:
    """コンテンツからフォーマットを検出"""
    content = content.strip()
    if content.startswith('{') or content.startswith('['):
        return 'json'
    elif content.startswith('<?xml') or content.startswith('<'):
        return 'xml'
    elif '---' in content[:20] or ': ' in content[:100]:
        # YAML or TOML
        if '[' in content and ']' in content and '=' in content:
            return 'toml'
        return 'yaml'
    elif ',' in content and '\n' in content:
        return 'csv'
    return 'unknown'


def parse_task_name(task_name: str) -> Tuple[str, str, str]:
    """タスク名から入力フォーマット、出力フォーマット、タイプを解析"""
    # "Text to JSON" -> ("text", "json", "generation")
    # "CSV to JSON" -> ("csv", "json", "conversion")
    parts = task_name.lower().split(' to ')
    if len(parts) == 2:
        input_fmt = parts[0].strip()
        output_fmt = parts[1].strip()
        if input_fmt == 'text':
            task_type = 'generation'
        else:
            task_type = 'conversion'
        return input_fmt, output_fmt, task_type
    return 'unknown', 'unknown', 'unknown'


def validate_format(content: str, expected_format: str) -> Tuple[bool, str]:
    """フォーマットが正しいか検証"""
    content = content.strip()

    if expected_format == 'json':
        try:
            json.loads(content)
            return True, "valid"
        except json.JSONDecodeError as e:
            return False, f"JSON parse error: {str(e)[:50]}"

    elif expected_format == 'xml':
        import xml.etree.ElementTree as ET
        try:
            ET.fromstring(content)
            return True, "valid"
        except ET.ParseError as e:
            return False, f"XML parse error: {str(e)[:50]}"

    elif expected_format == 'yaml':
        try:
            import yaml
            yaml.safe_load(content)
            return True, "valid"
        except:
            # YAMLパーサーがない場合は構文チェックのみ
            if ':' in content:
                return True, "likely valid (basic check)"
            return False, "YAML syntax error"

    elif expected_format == 'toml':
        try:
            import tomllib
            tomllib.loads(content)
            return True, "valid"
        except:
            if '=' in content and '[' in content:
                return True, "likely valid (basic check)"
            return False, "TOML syntax error"

    elif expected_format == 'csv':
        if ',' in content or '\t' in content:
            return True, "valid"
        return False, "CSV format error"

    return True, "unknown format"


# ========== 分析関数 ==========
def analyze_test_data(test_data: List[Dict]) -> Dict:
    """テストデータの分析"""
    print("=" * 70)
    print("テストデータ分析 (public_150.json)")
    print("=" * 70)

    analysis = {
        "total": len(test_data),
        "task_names": Counter(),
        "output_formats": Counter(),
        "task_types": Counter(),
        "complexity_by_task": defaultdict(list),
    }

    for item in test_data:
        task_name = item.get('task_name', 'unknown')
        analysis["task_names"][task_name] += 1

        input_fmt, output_fmt, task_type = parse_task_name(task_name)
        analysis["output_formats"][output_fmt] += 1
        analysis["task_types"][task_type] += 1

        # 入力テキストの長さを記録
        input_text = item.get('input', '')
        analysis["complexity_by_task"][task_name].append(len(input_text))

    print(f"\n総件数: {analysis['total']}")

    print(f"\n=== タスク名分布 ===")
    for task, count in sorted(analysis["task_names"].items(), key=lambda x: -x[1]):
        pct = count / analysis['total'] * 100
        print(f"  {task}: {count}件 ({pct:.1f}%)")

    print(f"\n=== 出力フォーマット分布 ===")
    for fmt, count in sorted(analysis["output_formats"].items(), key=lambda x: -x[1]):
        pct = count / analysis['total'] * 100
        print(f"  {fmt}: {count}件 ({pct:.1f}%)")

    print(f"\n=== タスクタイプ分布 ===")
    for task_type, count in sorted(analysis["task_types"].items(), key=lambda x: -x[1]):
        pct = count / analysis['total'] * 100
        print(f"  {task_type}: {count}件 ({pct:.1f}%)")

    return analysis


def analyze_inference_results(test_data: List[Dict], inference_data: Dict[str, List]) -> Dict:
    """推論結果の分析"""
    print("\n" + "=" * 70)
    print("推論結果分析")
    print("=" * 70)

    results = {}

    for version, inf_data in inference_data.items():
        print(f"\n--- {version} (スコア: {SCORES.get(version, '?')}) ---")

        version_result = {
            "valid_by_task": defaultdict(lambda: {"valid": 0, "invalid": 0}),
            "errors": [],
            "format_errors_by_type": Counter(),
        }

        for i, (test_item, inf_item) in enumerate(zip(test_data, inf_data)):
            task_name = test_item.get('task_name', 'unknown')
            _, output_fmt, _ = parse_task_name(task_name)

            # 推論結果を取得
            if isinstance(inf_item, dict):
                output = inf_item.get('generation', inf_item.get('output', ''))
            else:
                output = str(inf_item)

            # フォーマット検証
            is_valid, error_msg = validate_format(output, output_fmt)

            if is_valid:
                version_result["valid_by_task"][task_name]["valid"] += 1
            else:
                version_result["valid_by_task"][task_name]["invalid"] += 1
                version_result["errors"].append({
                    "index": i,
                    "task_name": task_name,
                    "error": error_msg,
                    "output_preview": output[:100] if output else "(empty)"
                })
                version_result["format_errors_by_type"][task_name] += 1

        # 結果表示
        total_valid = sum(v["valid"] for v in version_result["valid_by_task"].values())
        total_invalid = sum(v["invalid"] for v in version_result["valid_by_task"].values())
        print(f"  フォーマット有効率: {total_valid}/{total_valid+total_invalid} ({total_valid/(total_valid+total_invalid)*100:.1f}%)")

        if version_result["format_errors_by_type"]:
            print(f"  エラー多発タスク:")
            for task, count in version_result["format_errors_by_type"].most_common(5):
                print(f"    {task}: {count}件")

        results[version] = version_result

    return results


def compare_versions(test_data: List[Dict], inference_data: Dict[str, List]) -> None:
    """バージョン間の比較"""
    print("\n" + "=" * 70)
    print("バージョン間比較（v0 vs v1 vs v2）")
    print("=" * 70)

    # 各問題ごとの正解/不正解パターンを分析
    v0_data = inference_data.get("v0", [])
    v1_data = inference_data.get("v1", [])
    v2_data = inference_data.get("v2", [])

    patterns = Counter()
    improvement_cases = []
    regression_cases = []

    for i, test_item in enumerate(test_data):
        task_name = test_item.get('task_name', 'unknown')
        _, output_fmt, _ = parse_task_name(task_name)

        # 各バージョンの結果を取得
        results = {}
        for version, data in [("v0", v0_data), ("v1", v1_data), ("v2", v2_data)]:
            if i < len(data):
                output = data[i].get('generation', '') if isinstance(data[i], dict) else str(data[i])
                is_valid, _ = validate_format(output, output_fmt)
                results[version] = is_valid
            else:
                results[version] = None

        # パターンを記録
        pattern = f"v0:{results.get('v0', '?')}, v1:{results.get('v1', '?')}, v2:{results.get('v2', '?')}"
        patterns[pattern] += 1

        # v0→v2で改善したケース
        if results.get('v0') == False and results.get('v2') == True:
            improvement_cases.append({
                "index": i,
                "task_name": task_name,
            })

        # v0→v2で悪化したケース
        if results.get('v0') == True and results.get('v2') == False:
            regression_cases.append({
                "index": i,
                "task_name": task_name,
            })

    print(f"\n=== 結果パターン分布 ===")
    for pattern, count in patterns.most_common():
        print(f"  {pattern}: {count}件")

    print(f"\n=== v0→v2で改善したケース ({len(improvement_cases)}件) ===")
    improvement_by_task = Counter(c["task_name"] for c in improvement_cases)
    for task, count in improvement_by_task.most_common():
        print(f"  {task}: {count}件")

    print(f"\n=== v0→v2で悪化したケース ({len(regression_cases)}件) ===")
    regression_by_task = Counter(c["task_name"] for c in regression_cases)
    for task, count in regression_by_task.most_common():
        print(f"  {task}: {count}件")


def analyze_sft_data_coverage(test_data: List[Dict], sft_data: List[Dict]) -> None:
    """SFTデータのテストデータカバレッジを分析"""
    print("\n" + "=" * 70)
    print("SFTデータカバレッジ分析")
    print("=" * 70)

    # テストデータのタスク分布
    test_tasks = Counter()
    for item in test_data:
        task_name = item.get('task_name', 'unknown')
        test_tasks[task_name] += 1

    # SFTデータの分布
    sft_distribution = {
        "format": Counter(),
        "type": Counter(),
        "complexity": Counter(),
    }

    for item in sft_data:
        meta = item.get('metadata', {})
        sft_distribution["format"][meta.get('format', 'unknown')] += 1
        sft_distribution["type"][meta.get('type', 'unknown')] += 1
        sft_distribution["complexity"][meta.get('complexity', 'unknown')] += 1

    # テストタスクとSFTデータの対応マッピング
    task_to_sft = {
        "Text to JSON": {"type": "generation", "format": "json"},
        "Text to YAML": {"type": "generation", "format": "yaml"},
        "Text to XML": {"type": "generation", "format": "xml"},
        "Text to TOML": {"type": "generation", "format": "toml"},
        "Text to CSV": {"type": "generation", "format": "csv"},
        "CSV to JSON": {"type": "conversion", "format": "json"},
        "JSON to YAML": {"type": "conversion", "format": "yaml"},
        "XML to JSON": {"type": "conversion", "format": "json"},
        "YAML to JSON": {"type": "conversion", "format": "json"},
        "TOML to JSON": {"type": "conversion", "format": "json"},
        "TOML to YAML": {"type": "conversion", "format": "yaml"},
        "CSV to YAML": {"type": "conversion", "format": "yaml"},
        "XML to YAML": {"type": "conversion", "format": "yaml"},
    }

    print(f"\nSFTデータ総数: {len(sft_data)}")

    print("\n=== SFTフォーマット分布 ===")
    for fmt, count in sorted(sft_distribution["format"].items(), key=lambda x: -x[1]):
        pct = count / len(sft_data) * 100
        print(f"  {fmt}: {count}件 ({pct:.1f}%)")

    print("\n=== SFTタイプ分布 ===")
    for task_type, count in sorted(sft_distribution["type"].items(), key=lambda x: -x[1]):
        pct = count / len(sft_data) * 100
        print(f"  {task_type}: {count}件 ({pct:.1f}%)")

    print("\n=== テストタスク vs SFTデータ対応 ===")
    print(f"{'テストタスク':<20} {'テスト件数':>10} {'SFT件数':>10} {'カバー率':>10}")
    print("-" * 55)

    coverage_issues = []
    for task_name, test_count in sorted(test_tasks.items(), key=lambda x: -x[1]):
        sft_mapping = task_to_sft.get(task_name, {})
        sft_type = sft_mapping.get("type", "unknown")
        sft_format = sft_mapping.get("format", "unknown")

        # SFTデータで対応するデータを数える
        sft_count = sum(1 for item in sft_data
                       if item.get('metadata', {}).get('type') == sft_type
                       and item.get('metadata', {}).get('format') == sft_format)

        coverage_ratio = sft_count / test_count if test_count > 0 else 0
        print(f"{task_name:<20} {test_count:>10} {sft_count:>10} {coverage_ratio:>10.1f}x")

        if coverage_ratio < 10:  # 10倍未満は要注意
            coverage_issues.append({
                "task": task_name,
                "test_count": test_count,
                "sft_count": sft_count,
                "ratio": coverage_ratio
            })

    if coverage_issues:
        print(f"\n=== カバレッジ不足のタスク（10x未満） ===")
        for issue in coverage_issues:
            print(f"  {issue['task']}: テスト{issue['test_count']}件に対しSFT{issue['sft_count']}件 ({issue['ratio']:.1f}x)")


def suggest_data_strategy(test_analysis: Dict, inference_results: Dict, sft_data: List[Dict]) -> None:
    """データ増減戦略を提案"""
    print("\n" + "=" * 70)
    print("v5データ戦略提案")
    print("=" * 70)

    # スコア推移の分析
    print("\n=== スコア推移 ===")
    print("  v0 (3,933件): {SCORES['v0']}")
    print("  v1 (3,933件): {SCORES['v1']} (過学習で悪化)")
    print("  v2 (3,933件): {SCORES['v2']} (最高スコア)")

    # 推論結果から問題のあるタスクを特定
    v2_results = inference_results.get("v2", {})
    problem_tasks = []
    for task_name, stats in v2_results.get("valid_by_task", {}).items():
        invalid_rate = stats["invalid"] / (stats["valid"] + stats["invalid"]) if (stats["valid"] + stats["invalid"]) > 0 else 0
        if invalid_rate > 0.2:  # 20%以上のエラー率
            problem_tasks.append({
                "task": task_name,
                "invalid_rate": invalid_rate,
                "invalid_count": stats["invalid"]
            })

    print(f"\n=== 問題のあるタスク（v2でエラー率20%以上） ===")
    if problem_tasks:
        for pt in sorted(problem_tasks, key=lambda x: -x["invalid_rate"]):
            print(f"  {pt['task']}: エラー率{pt['invalid_rate']*100:.1f}% ({pt['invalid_count']}件)")
    else:
        print("  なし")

    # 戦略提案
    print("\n=== データ戦略提案 ===")

    print("\n【方針1】データを減らす戦略（品質重視）")
    print("  - XMLエラーを含むデータを除去（64件→3,869件）")
    print("  - v2の成功を踏まえ、3,500-4,000件程度を維持")
    print("  - 期待効果: XMLバリデーションエラーの削減")

    print("\n【方針2】データを増やす戦略（カバレッジ重視）")
    print("  - Conversionタスクのデータを増強")
    print("  - 他のデータセット（1-2_512_v4等）から類似データを追加")
    print("  - 注意: v3で8,541件に増やしてスコア低下した教訓あり")

    print("\n【方針3】ハイパーパラメータ調整（データ量維持）")
    print("  - Epoch=2（Person Eの成功例）")
    print("  - プロンプト改良（コードフェンス/前置き文の抑制）")
    print("  - データ量は現状維持（3,869件）")

    print("\n【推奨】")
    print("  v5では「方針1 + 方針3」の組み合わせを推奨：")
    print("  1. XMLエラーデータ除去（3,869件）")
    print("  2. Epoch=2で学習")
    print("  3. プロンプト改良")
    print("  理由: v3でデータ増加が逆効果だった教訓から、")
    print("        データ品質向上とハイパーパラメータ調整に注力")


def detailed_error_analysis(test_data: List[Dict], inference_data: Dict[str, List]) -> None:
    """詳細なエラー分析"""
    print("\n" + "=" * 70)
    print("詳細エラー分析")
    print("=" * 70)

    v2_data = inference_data.get("v2", [])

    errors_by_format = defaultdict(list)

    for i, test_item in enumerate(test_data):
        task_name = test_item.get('task_name', 'unknown')
        _, output_fmt, _ = parse_task_name(task_name)

        if i < len(v2_data):
            output = v2_data[i].get('output', '') if isinstance(v2_data[i], dict) else str(v2_data[i])
            is_valid, error_msg = validate_format(output, output_fmt)

            if not is_valid:
                errors_by_format[output_fmt].append({
                    "index": i,
                    "task_name": task_name,
                    "error": error_msg,
                    "output_preview": output[:200] if output else "(empty)",
                    "input_preview": test_item.get('input', '')[:100]
                })

    for fmt, errors in errors_by_format.items():
        print(f"\n=== {fmt.upper()}フォーマットのエラー ({len(errors)}件) ===")
        for err in errors[:3]:  # 最大3件表示
            print(f"\n  インデックス: {err['index']}")
            print(f"  タスク: {err['task_name']}")
            print(f"  エラー: {err['error']}")
            print(f"  出力プレビュー: {err['output_preview'][:100]}...")


# ========== メイン処理 ==========
def main():
    print("v5戦略分析スクリプト")
    print("=" * 70)

    # データ読み込み
    print("\nデータを読み込み中...")
    test_data = load_json(TEST_DATA_PATH)
    print(f"  テストデータ: {len(test_data)}件")

    inference_data = {}
    for version, path in INFERENCE_PATHS.items():
        if os.path.exists(path):
            inference_data[version] = load_json(path)
            print(f"  {version}推論結果: {len(inference_data[version])}件")
        else:
            print(f"  {version}推論結果: ファイルなし")

    sft_data = load_json(SFT_DATA_PATH)
    print(f"  SFTデータ: {len(sft_data)}件")

    # 分析実行
    test_analysis = analyze_test_data(test_data)
    inference_results = analyze_inference_results(test_data, inference_data)
    compare_versions(test_data, inference_data)
    analyze_sft_data_coverage(test_data, sft_data)
    detailed_error_analysis(test_data, inference_data)
    suggest_data_strategy(test_analysis, inference_results, sft_data)


if __name__ == "__main__":
    main()
