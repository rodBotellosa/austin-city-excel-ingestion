"""
Semantic path builder that creates meaningful content hierarchies based on subtitles.
"""

import json
import re
from typing import List, Dict, Any, Optional
from pathlib import Path


def clean_subtitle_for_path(subtitle: str) -> str:
    """
    Clean subtitle text to create meaningful path segments while preserving semantic meaning.
    """
    if not subtitle:
        return ""
    
    # Remove common prefixes that don't add semantic value
    subtitle = re.sub(r'^(Section|Sec\.|Chapter|Ch\.|Part|P\.)\s*', '', subtitle, flags=re.IGNORECASE)
    
    # Clean up the text for path usage - keep spaces for semantic meaning
    # Convert to lowercase and remove only problematic special chars, keep spaces
    cleaned = re.sub(r'[^\w\s]', '', subtitle.lower())
    cleaned = re.sub(r'\s+', ' ', cleaned)  # Normalize multiple spaces to single space
    cleaned = cleaned.strip()
    
    return cleaned if cleaned else "untitled"


def build_semantic_path(record: Dict[str, Any], all_records: List[Dict[str, Any]]) -> List[str]:
    """
    Build semantic path based on subtitle and hierarchical relationships without numerical prefixes.
    """
    title = record.get('title', '')
    subtitle = record.get('subtitle', '')
    parent_anchor = record.get('parent_anchor', '')
    
    if not subtitle:
        # If no subtitle, try to create one from title
        if title and re.match(r'^\d+(\.\d+)*$', title):
            # For numeric titles, create a generic subtitle
            subtitle = f"Section {title}"
        else:
            subtitle = title or "Untitled"
    
    # Start building the semantic path
    semantic_path = []
    
    # Check if this is a top-level section
    if re.match(r'^SECTION\s+\d+', subtitle, re.IGNORECASE):
        # Top-level section - just use the cleaned subtitle without numerical prefix
        semantic_path.append(clean_subtitle_for_path(subtitle))
    else:
        # Find the parent record to build the path
        if parent_anchor:
            parent_record = find_record_by_anchor(all_records, parent_anchor)
            if parent_record:
                # Recursively build parent's semantic path
                parent_semantic_path = build_semantic_path(parent_record, all_records)
                semantic_path.extend(parent_semantic_path)
        
        # Add current subtitle to the path, but exclude numeric titles
        # Only add subtitle if it's not just a numeric title
        if not (title and re.match(r'^\d+(\.\d+)*$', title)):
            # This is a descriptive title, add it to the path
            semantic_path.append(clean_subtitle_for_path(subtitle))
        else:
            # This is a numeric title, skip adding it to semantic path
            # But still process the subtitle if it exists
            if subtitle and not re.match(r'^\d+(\.\d+)*$', subtitle):
                semantic_path.append(clean_subtitle_for_path(subtitle))
    
    return semantic_path


def find_record_by_anchor(records: List[Dict[str, Any]], anchor: str) -> Optional[Dict[str, Any]]:
    """
    Find a record by its anchor.
    """
    for record in records:
        if record.get('anchor') == anchor:
            return record
    return None


def enhance_records_with_semantic_paths(input_file: str, output_file: str) -> None:
    """
    Process JSONL file and add semantic paths based on subtitles.
    """
    print(f"Processing {input_file} to add semantic paths...")
    
    # Read all records first to build relationships
    records = []
    with open(input_file, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            try:
                record = json.loads(line.strip())
                records.append(record)
            except json.JSONDecodeError as e:
                print(f"Error parsing line {line_num}: {e}")
                continue
    
    print(f"Loaded {len(records)} records")
    
    # Sort records by order to ensure proper hierarchy building
    records.sort(key=lambda x: x.get('order', 0))
    
    # Build semantic paths for each record
    enhanced_records = []
    for record in records:
        # Build semantic path
        semantic_path = build_semantic_path(record, records)
        
        # Add semantic path to record
        record['semantic_path'] = semantic_path
        
        # Create a human-readable semantic path string
        record['semantic_path_string'] = ' > '.join(semantic_path)
        

        
        enhanced_records.append(record)
    
    # Write enhanced records
    with open(output_file, 'w', encoding='utf-8') as f:
        for record in enhanced_records:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')
    
    print(f"Enhanced {len(enhanced_records)} records with semantic paths")
    print(f"Output written to: {output_file}")
    
    # Show some examples
    print("\n=== Semantic Path Examples ===")
    for record in enhanced_records[:5]:
        if record.get('semantic_path'):
            print(f"Title: {record.get('title', 'N/A')}")
            print(f"Subtitle: {record.get('subtitle', 'N/A')}")
            print(f"Semantic Path: {' > '.join(record['semantic_path'])}")
            print()


def create_semantic_path_index(records: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """
    Create an index of semantic paths for quick lookup.
    """
    index = {}
    
    for record in records:
        semantic_path = record.get('semantic_path', [])
        if semantic_path:
            # Create key from semantic path
            key = ' > '.join(semantic_path)
            if key not in index:
                index[key] = []
            index[key].append(record['anchor'])
    
    return index


def main():
    """Main function for command line usage."""
    import sys
    
    if len(sys.argv) != 3:
        print("Usage: python semantic_path_builder.py <input.jsonl> <output.jsonl>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    
    if not Path(input_file).exists():
        print(f"Error: Input file {input_file} not found!")
        sys.exit(1)
    
    enhance_records_with_semantic_paths(input_file, output_file)


if __name__ == "__main__":
    main() 