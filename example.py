#!/usr/bin/env python3
"""
Example script demonstrating how to use the Austin City Excel Ingestion Tool.
"""

import json
from pathlib import Path

from src.excel_parser import ExcelParser
from src.models import ExcelIngestionConfig


def main():
    """Example usage of the Excel ingestion tool."""
    
    # Configuration
    excel_file = "sample_data.xlsx"  # Replace with your Excel file
    output_prefix = "processed_data"
    
    try:
        # Create configuration
        config = ExcelIngestionConfig(
            doc_id="ecm",
            output_format="both",  # Generate both JSONL and Parquet
            normalize_anchors=True
        )
        
        print(f"Starting Excel ingestion: {excel_file}")
        
        # Initialize parser
        parser = ExcelParser(config)
        
        # Parse Excel file
        print("Parsing Excel file...")
        rows = parser.parse_excel_file(excel_file)
        
        # Write output
        print("Writing output files...")
        parser.write_output(rows, output_prefix)
        
        # Print summary
        print(f"\n=== INGESTION COMPLETE ===")
        print(f"Total rows processed: {len(rows)}")
        print(f"Output files:")
        print(f"  JSONL: {output_prefix}.jsonl")
        print(f"  Parquet: {output_prefix}.parquet")
        
        # Show statistics
        print(f"\n=== PROCESSING STATISTICS ===")
        
        # Block type distribution
        block_types = {}
        for row in rows:
            block_type = row.block_type
            block_types[block_type] = block_types.get(block_type, 0) + 1
        
        print("Block type distribution:")
        for block_type, count in sorted(block_types.items()):
            percentage = (count / len(rows)) * 100
            print(f"  {block_type}: {count} ({percentage:.1f}%)")
        
        # Confidence distribution
        high_conf = len([r for r in rows if r.confidence >= 0.8])
        medium_conf = len([r for r in rows if 0.6 <= r.confidence < 0.8])
        low_conf = len([r for r in rows if r.confidence < 0.6])
        
        print(f"\nConfidence distribution:")
        print(f"  High (≥0.8): {high_conf} ({high_conf/len(rows)*100:.1f}%)")
        print(f"  Medium (0.6-0.8): {medium_conf} ({medium_conf/len(rows)*100:.1f}%)")
        print(f"  Low (<0.6): {low_conf} ({low_conf/len(rows)*100:.1f}%)")
        
        # Reference statistics
        total_refs = sum(len(row.refs) for row in rows)
        rows_with_refs = len([r for r in rows if r.refs])
        
        print(f"\nReferences:")
        print(f"  Total references: {total_refs}")
        print(f"  Rows with references: {rows_with_refs} ({rows_with_refs/len(rows)*100:.1f}%)")
        
        # Show sample output
        print(f"\n=== SAMPLE OUTPUT ===")
        if rows:
            sample_row = rows[0]
            print("Sample row:")
            print(json.dumps(sample_row.dict(), indent=2))
        
        # Show hierarchy example
        print(f"\n=== HIERARCHY EXAMPLE ===")
        headings = [r for r in rows if r.block_type == "HEADING"][:5]
        for heading in headings:
            indent = "  " * (len(heading.path) - 1)
            print(f"{indent}{heading.anchor}: {heading.title}")
        
    except FileNotFoundError:
        print(f"Error: Excel file '{excel_file}' not found.")
        print("Please create a sample Excel file with the required columns:")
        print("  - NodeId (required)")
        print("  - Title (optional)")
        print("  - Subtitle (optional)")
        print("  - Content (optional)")
        print("  - Url (optional)")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


def create_sample_excel():
    """Create a sample Excel file for testing."""
    import pandas as pd
    
    # Sample data
    data = {
        'NodeId': ['1', '1.1', '1.2', '1.2.1', '1.2.1.1'],
        'Title': ['General', 'Purpose', 'Environmental Resource Inventory', 'Definitions', 'Fiscal Surety Calculations'],
        'Subtitle': ['', '', '', '', ''],
        'Content': [
            '',
            'This section defines the purpose and scope of the Environmental Criteria Manual.',
            '',
            'Section 25-8-184 defines the following terms for the purposes of this manual.',
            'A. Fiscal surety required by the City shall be determined by LDC 25-8-514.'
        ],
        'Url': ['', '', 'https://example.com', '', '']
    }
    
    df = pd.DataFrame(data)
    df.to_excel('sample_data.xlsx', index=False)
    print("Created sample_data.xlsx")


if __name__ == "__main__":
    # Uncomment the next line to create a sample Excel file
    # create_sample_excel()
    
    main() 