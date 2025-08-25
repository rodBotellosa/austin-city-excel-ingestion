#!/usr/bin/env python3
"""
Script to clean up content field in JSON output for better storage efficiency and readability.
"""

import json
import re
from pathlib import Path


def clean_content(content):
    """Clean up content text for better readability and storage efficiency."""
    if not content:
        return None
    
    # Remove excessive whitespace and normalize
    content = re.sub(r'\s+', ' ', content.strip())
    
    # Remove HTML-like entities
    content = re.sub(r'&nbsp;', ' ', content)
    content = re.sub(r'&amp;', '&', content)
    content = re.sub(r'&lt;', '<', content)
    content = re.sub(r'&gt;', '>', content)
    
    # Clean up bullet points and lists
    content = re.sub(r'•\s*', '• ', content)
    content = re.sub(r'-\s*', '- ', content)
    
    # Remove excessive newlines and formatting
    content = re.sub(r'\n\s*\n', '\n\n', content)
    content = re.sub(r'\s*\n\s*', '\n', content)
    
    # Clean up section markers
    content = re.sub(r'([A-Z]\.)\s*\n\s*', r'\1 ', content)
    content = re.sub(r'(\d+\.)\s*\n\s*', r'\1 ', content)
    
    # Remove table-like formatting
    content = re.sub(r'\s*\|\s*', ' | ', content)
    
    # Clean up parentheses and brackets
    content = re.sub(r'\(\s+', '(', content)
    content = re.sub(r'\s+\)', ')', content)
    content = re.sub(r'\[\s+', '[', content)
    content = re.sub(r'\s+\]', ']', content)
    
    # Remove excessive spaces around punctuation
    content = re.sub(r'\s+([.,;:!?])', r'\1', content)
    content = re.sub(r'([.,;:!?])\s+', r'\1 ', content)
    
    # Clean up quotes
    content = re.sub(r'"\s+', '"', content)
    content = re.sub(r'\s+"', '"', content)
    
    # Remove redundant spaces
    content = re.sub(r' +', ' ', content)
    
    return content.strip()


def process_json_file(input_file, output_file):
    """Process JSON file and clean up content fields."""
    print(f"Processing {input_file}...")
    
    # Read the JSON file
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Process each record
    processed_count = 0
    for record in data:
        if 'content' in record and record['content']:
            original_length = len(record['content'])
            record['content'] = clean_content(record['content'])
            if record['content']:
                new_length = len(record['content'])
                reduction = original_length - new_length
                if reduction > 0:
                    processed_count += 1
                    print(f"  Cleaned content for {record.get('anchor', 'unknown')}: "
                          f"{original_length} -> {new_length} chars "
                          f"({reduction} chars saved)")
    
    # Write the cleaned data
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"Processed {processed_count} records")
    print(f"Output written to {output_file}")


def main():
    """Main function."""
    input_file = "prettified_output.json"
    output_file = "cleaned_output.json"
    
    if not Path(input_file).exists():
        print(f"Error: {input_file} not found!")
        return
    
    process_json_file(input_file, output_file)


if __name__ == "__main__":
    main() 