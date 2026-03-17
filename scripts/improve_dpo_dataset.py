#!/usr/bin/env python3
"""
DPO Dataset Improvement Script

This script improves the DPO training data by:
1. Removing system prompts (to match inference conditions)
2. Optimizing chosen responses (code-only output, no explanations/markdown)

Input: inputs/dpo/train.json
Output: inputs/dpo_processed/v1/train.json
"""
import json
import re
import argparse
from pathlib import Path
from typing import Dict, Tuple, Any


def remove_system_prompt(prompt: str) -> str:
    """
    Remove system prompt from the prompt string.

    Before: <|im_start|>system\n...<|im_end|>\n<|im_start|>user\n...<|im_end|>\n<|im_start|>assistant\n
    After: <|im_start|>user\n...<|im_end|>\n<|im_start|>assistant\n
    """
    # Pattern to match the entire system section
    pattern = r'<\|im_start\|>system\n.*?<\|im_end\|>\n'
    cleaned = re.sub(pattern, '', prompt, flags=re.DOTALL)
    return cleaned


def extract_code_from_chosen(chosen: str) -> Tuple[str, bool]:
    """
    Extract only the code portion from chosen response.

    Before: Approach:\n1. ...\n...\n\nOutput:\n[code]
    After: [code]

    Returns:
        Tuple of (extracted_code, was_modified)
    """
    # Pattern to match "Approach:...Output:\n" and extract what comes after
    # The Output: marker should be followed by the actual code
    pattern = r'^Approach:.*?Output:\n'

    match = re.match(pattern, chosen, flags=re.DOTALL)
    if match:
        code = chosen[match.end():]
        # Remove trailing whitespace but keep necessary newlines in code
        code = code.rstrip()
        return code, True

    # If no match, return original (shouldn't happen based on analysis)
    return chosen, False


def analyze_response(response: str) -> Dict[str, bool]:
    """Analyze a response for various patterns."""
    return {
        'has_approach': 'Approach:' in response,
        'has_output': 'Output:' in response,
        'has_markdown': '```' in response,
        'starts_with_sure': response.strip().startswith('Sure'),
        'has_here': "Here's" in response or "Here is" in response,
    }


def process_dataset(input_path: str, output_path: str, verbose: bool = True) -> Dict[str, Any]:
    """
    Process the DPO dataset and apply improvements.

    Args:
        input_path: Path to input JSON file
        output_path: Path to output JSON file
        verbose: Whether to print progress information

    Returns:
        Statistics dictionary
    """
    # Load data
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    stats = {
        'total_samples': len(data),
        'system_prompts_removed': 0,
        'chosen_code_extracted': 0,
        'chosen_unchanged': 0,
        'original_chosen_patterns': {
            'has_approach': 0,
            'has_output': 0,
            'has_markdown': 0,
        },
        'original_rejected_patterns': {
            'has_approach': 0,
            'has_output': 0,
            'has_markdown': 0,
        },
        'improved_chosen_patterns': {
            'has_approach': 0,
            'has_output': 0,
            'has_markdown': 0,
        },
    }

    improved_data = []

    for i, item in enumerate(data):
        # Analyze original patterns
        orig_chosen_analysis = analyze_response(item['chosen'])
        orig_rejected_analysis = analyze_response(item['rejected'])

        for key in ['has_approach', 'has_output', 'has_markdown']:
            if orig_chosen_analysis[key]:
                stats['original_chosen_patterns'][key] += 1
            if orig_rejected_analysis[key]:
                stats['original_rejected_patterns'][key] += 1

        # Process prompt - remove system prompt
        original_prompt = item['prompt']
        improved_prompt = remove_system_prompt(original_prompt)

        if improved_prompt != original_prompt:
            stats['system_prompts_removed'] += 1

        # Process chosen - extract code only
        original_chosen = item['chosen']
        improved_chosen, was_modified = extract_code_from_chosen(original_chosen)

        if was_modified:
            stats['chosen_code_extracted'] += 1
        else:
            stats['chosen_unchanged'] += 1

        # Analyze improved chosen
        improved_chosen_analysis = analyze_response(improved_chosen)
        for key in ['has_approach', 'has_output', 'has_markdown']:
            if improved_chosen_analysis[key]:
                stats['improved_chosen_patterns'][key] += 1

        # Create improved item
        improved_item = {
            'prompt': improved_prompt,
            'chosen': improved_chosen,
            'rejected': item['rejected'],  # Keep rejected as-is
            'strategy': item.get('strategy', 'model_generated'),
        }

        improved_data.append(improved_item)

        # Progress indicator
        if verbose and (i + 1) % 1000 == 0:
            print(f"Processed {i + 1}/{len(data)} samples...")

    # Validate JSON output
    try:
        json_str = json.dumps(improved_data, ensure_ascii=False, indent=2)
        # Verify it can be parsed back
        json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"Generated invalid JSON: {e}")

    # Save improved data
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(json_str)

    return stats


def print_report(stats: Dict[str, Any], input_path: str, output_path: str):
    """Print a detailed statistics report."""
    print("\n" + "=" * 70)
    print("DPO DATASET IMPROVEMENT REPORT")
    print("=" * 70)

    print(f"\n📁 Input: {input_path}")
    print(f"📁 Output: {output_path}")

    print("\n📊 PROCESSING STATISTICS")
    print("-" * 40)
    print(f"Total samples processed: {stats['total_samples']}")
    print(f"System prompts removed: {stats['system_prompts_removed']}")
    print(f"Chosen responses with code extracted: {stats['chosen_code_extracted']}")
    print(f"Chosen responses unchanged: {stats['chosen_unchanged']}")

    print("\n📋 ORIGINAL CHOSEN RESPONSE PATTERNS")
    print("-" * 40)
    for key, value in stats['original_chosen_patterns'].items():
        print(f"  {key}: {value}")

    print("\n📋 ORIGINAL REJECTED RESPONSE PATTERNS")
    print("-" * 40)
    for key, value in stats['original_rejected_patterns'].items():
        print(f"  {key}: {value}")

    print("\n✅ IMPROVED CHOSEN RESPONSE PATTERNS")
    print("-" * 40)
    for key, value in stats['improved_chosen_patterns'].items():
        print(f"  {key}: {value}")

    print("\n" + "=" * 70)
    print("IMPROVEMENT SUMMARY")
    print("=" * 70)

    # Calculate improvements
    approach_removed = stats['original_chosen_patterns']['has_approach'] - stats['improved_chosen_patterns']['has_approach']
    output_removed = stats['original_chosen_patterns']['has_output'] - stats['improved_chosen_patterns']['has_output']

    print("\n🔧 Changes applied:")
    print(f"  1. System prompts removed from prompts: {stats['system_prompts_removed']}/{stats['total_samples']}")
    print(f"  2. 'Approach:' removed from chosen: {approach_removed}/{stats['total_samples']}")
    print(f"  3. 'Output:' removed from chosen: {output_removed}/{stats['total_samples']}")
    print("  4. Rejected responses kept as-is (with explanations/markdown)")

    print("\n💡 Expected benefits:")
    print("  - Model will learn to output code directly without explanations")
    print("  - Training conditions now match inference conditions (no system prompt)")
    print("  - Clear contrast between chosen (code-only) and rejected (with explanations)")

    print("\n" + "=" * 70)


def show_sample_comparison(input_path: str, output_path: str, sample_idx: int = 0):
    """Show a side-by-side comparison of original vs improved data."""
    with open(input_path, 'r', encoding='utf-8') as f:
        original = json.load(f)

    with open(output_path, 'r', encoding='utf-8') as f:
        improved = json.load(f)

    print("\n" + "=" * 70)
    print(f"SAMPLE COMPARISON (index={sample_idx})")
    print("=" * 70)

    print("\n📌 ORIGINAL PROMPT:")
    print("-" * 40)
    print(original[sample_idx]['prompt'][:500])
    print("..." if len(original[sample_idx]['prompt']) > 500 else "")

    print("\n📌 IMPROVED PROMPT (system removed):")
    print("-" * 40)
    print(improved[sample_idx]['prompt'][:500])
    print("..." if len(improved[sample_idx]['prompt']) > 500 else "")

    print("\n📌 ORIGINAL CHOSEN:")
    print("-" * 40)
    print(original[sample_idx]['chosen'][:500])
    print("..." if len(original[sample_idx]['chosen']) > 500 else "")

    print("\n📌 IMPROVED CHOSEN (code only):")
    print("-" * 40)
    print(improved[sample_idx]['chosen'][:500])
    print("..." if len(improved[sample_idx]['chosen']) > 500 else "")


def main():
    parser = argparse.ArgumentParser(
        description='Improve DPO dataset by removing system prompts and extracting code-only responses'
    )
    parser.add_argument(
        '--input', '-i',
        default='inputs/dpo/train.json',
        help='Input JSON file path (default: inputs/dpo/train.json)'
    )
    parser.add_argument(
        '--output', '-o',
        default='inputs/dpo_processed/v1/train.json',
        help='Output JSON file path (default: inputs/dpo_processed/v1/train.json)'
    )
    parser.add_argument(
        '--sample', '-s',
        type=int,
        default=0,
        help='Sample index to show in comparison (default: 0)'
    )
    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Suppress progress output'
    )

    args = parser.parse_args()

    # Verify input file exists
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ Error: Input file not found: {args.input}")
        return 1

    # Create output directory if needed
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print("🚀 Processing DPO dataset...")
    print(f"   Input: {args.input}")
    print(f"   Output: {args.output}")

    # Process dataset
    stats = process_dataset(args.input, args.output, verbose=not args.quiet)

    # Print report
    print_report(stats, args.input, args.output)

    # Show sample comparison
    show_sample_comparison(args.input, args.output, args.sample)

    print(f"\n✅ Successfully created improved dataset: {args.output}")

    return 0


if __name__ == '__main__':
    exit(main())
