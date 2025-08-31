#!/usr/bin/env python3
"""
Workflow script that combines semantic path building and hierarchical chunking.
"""

import sys
from pathlib import Path
from semantic_path_builder import enhance_records_with_semantic_paths
from chunker import process_jsonl_with_chunking


def main():
    """Main workflow: semantic paths -> chunking."""
    if len(sys.argv) != 2:
        print("Usage: python process_workflow.py <input.jsonl>")
        print("This will create:")
        print("  <input>_semantic.jsonl (with semantic paths)")
        print("  <input>_semantic_chunked.jsonl (final output)")
        sys.exit(1)
    
    input_file = sys.argv[1]
    
    if not Path(input_file).exists():
        print(f"Error: Input file {input_file} not found!")
        sys.exit(1)
    
    # Step 1: Add semantic paths
    print("=== Step 1: Adding Semantic Paths ===")
    semantic_file = input_file.replace('.jsonl', '_semantic.jsonl')
    enhance_records_with_semantic_paths(input_file, semantic_file)
    
    # Step 2: Apply hierarchical chunking
    print("\n=== Step 2: Applying Hierarchical Chunking ===")
    final_file = semantic_file.replace('.jsonl', '_chunked.jsonl')
    process_jsonl_with_chunking(semantic_file, final_file, max_tokens=300)
    
    print(f"\n=== Workflow Complete ===")
    print(f"Input: {input_file}")
    print(f"Semantic paths: {semantic_file}")
    print(f"Final output: {final_file}")
    print(f"\nYou can now use the final output for lexical search!")


if __name__ == "__main__":
    main() 