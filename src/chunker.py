"""
Hierarchical chunking module for breaking down long content into semantic chunks.
"""

import re
import hashlib
import json
from typing import List, Dict, Any, Optional
from datetime import datetime

try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False


def split_on_semantic_boundaries(text: str) -> List[str]:
    """
    Split text on semantic boundaries in order of priority:
    1. Top-level letters/subsections (A., B., C.)
    2. Numbered items (1., (1), I., (I))
    3. Bullets (•, -, –, *)
    """
    if not text:
        return []
    
    # Split by top-level letters/subsections (A., B., C.)
    letter_pattern = r'^([A-Z]\.\s+)'
    if re.search(letter_pattern, text, re.MULTILINE):
        parts = re.split(letter_pattern, text)
        # Rejoin the delimiter with its content
        result = []
        for i in range(1, len(parts), 2):
            if i + 1 < len(parts):
                result.append(parts[i] + parts[i + 1])
            else:
                result.append(parts[i])
        if result:
            return result
    
    # Split by numbered items (1., (1), I., (I))
    number_pattern = r'^((?:\(?\d+\)?\.?\s+)|(?:\(?[IVX]+\)?\.?\s+))'
    if re.search(number_pattern, text, re.MULTILINE):
        parts = re.split(number_pattern, text)
        result = []
        for i in range(1, len(parts), 2):
            if i + 1 < len(parts):
                result.append(parts[i] + parts[i + 1])
            else:
                result.append(parts[i])
        if result:
            return result
    
    # Split by bullets (•, -, –, *)
    bullet_pattern = r'^([•\-–*]\s+)'
    if re.search(bullet_pattern, text, re.MULTILINE):
        parts = re.split(bullet_pattern, text)
        result = []
        for i in range(1, len(parts), 2):
            if i + 1 < len(parts):
                result.append(parts[i] + parts[i + 1])
            else:
                result.append(parts[i])
        if result:
            return result
    
    # If no semantic boundaries found, return the original text
    return [text]


def tokenize_len(text: str) -> int:
    """
    Get token count using tiktoken (GPT-4o mini encoding) if available;
    fallback to simple whitespace count * 0.75 as estimate.
    """
    if TIKTOKEN_AVAILABLE:
        try:
            encoding = tiktoken.get_encoding("cl100k_base")  # GPT-4o mini encoding
            return len(encoding.encode(text))
        except Exception:
            pass
    
    # Fallback: simple whitespace-based estimate
    words = text.split()
    return int(len(words) * 0.75)


def window_chunks(text: str, target: int = 250, max_len: int = 320, overlap: int = 40) -> List[str]:
    """
    Split text into overlapping windows if it exceeds max_len.
    Preserves sentence boundaries and avoids breaking inside code/URLs.
    """
    if tokenize_len(text) <= max_len:
        return [text]
    
    # Split by sentences
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks = []
    current_chunk = ""
    
    for sentence in sentences:
        # Skip empty sentences
        if not sentence.strip():
            continue
        
        # Check if adding this sentence would exceed target
        test_chunk = current_chunk + " " + sentence if current_chunk else sentence
        if tokenize_len(test_chunk) <= target:
            current_chunk = test_chunk
        else:
            # Current chunk is ready
            if current_chunk:
                chunks.append(current_chunk.strip())
            
            # Start new chunk with overlap if possible
            if chunks and overlap > 0:
                # Get last few words from previous chunk for overlap
                last_words = chunks[-1].split()[-5:]  # Last 5 words
                overlap_text = " " + " ".join(last_words)
                current_chunk = overlap_text + " " + sentence
            else:
                current_chunk = sentence
    
    # Add the last chunk
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    return chunks


def chunk_content(text: str, max_len: int = 300) -> List[str]:
    """
    Split content into semantic chunks, then apply windowing if needed.
    Returns list of chunks, each ideally 150-300 tokens.
    """
    if not text:
        return []
    
    # First split on semantic boundaries
    semantic_parts = split_on_semantic_boundaries(text)
    
    # Then apply windowing to parts that are too long
    final_chunks = []
    for part in semantic_parts:
        if tokenize_len(part) <= max_len:
            final_chunks.append(part)
        else:
            # Apply windowing to this part
            windowed = window_chunks(part, target=250, max_len=max_len, overlap=40)
            final_chunks.extend(windowed)
    
    return final_chunks


def make_chunk_records(parent_record: Dict[str, Any], chunks: List[str]) -> List[Dict[str, Any]]:
    """
    Create chunk records from a parent record and its content chunks.
    If only one chunk, return parent unchanged. Otherwise create parent + children.
    """
    if len(chunks) == 1:
        # Update parent record with token count
        parent_record['tokens'] = tokenize_len(chunks[0])
        
        # Add semantic content field if semantic_path_string exists
        if parent_record.get('semantic_path_string'):
            if parent_record.get('content'):
                parent_record['semantic_content'] = f"{parent_record['semantic_path_string']} | {parent_record['content']}"
            else:
                parent_record['semantic_content'] = parent_record['semantic_path_string']
        
        return [parent_record]
    
    # Create parent record with children metadata
    parent_record['has_children'] = True
    parent_record['child_count'] = len(chunks)
    parent_record['tokens'] = sum(tokenize_len(chunk) for chunk in chunks)
    
    # Add semantic content field if semantic_path_string exists
    if parent_record.get('semantic_path_string'):
        if parent_record.get('content'):
            parent_record['semantic_content'] = f"{parent_record['semantic_path_string']} | {parent_record['content']}"
        else:
            parent_record['semantic_content'] = parent_record['semantic_path_string']
    
    # Create child records
    child_records = []
    for i, chunk in enumerate(chunks, 1):
        # Create child anchor (e.g., "1.2.1.1_A" for first chunk)
        child_anchor = f"{parent_record['anchor']}_{chr(64 + i)}"  # A, B, C, etc.
        
        # Create child record
        child_record = {
            "doc_id": parent_record['doc_id'],
            "anchor": child_anchor,
            "node_id": parent_record['node_id'],
            "title": parent_record['title'],
            "subtitle": parent_record['subtitle'],
            "content": chunk,
            "url": parent_record['url'],
            "path": parent_record['path'] + [child_anchor],
            "parent_anchor": parent_record['anchor'],
            "block_type": "PARA",  # Default to paragraph for chunks
            "section_labels": parent_record['section_labels'],
            "order": int(str(parent_record['order']) + f"{i:03d}"),  # Stable sortable
            "tokens": tokenize_len(chunk),
            "confidence": calculate_chunk_confidence(chunk),
            "refs": extract_chunk_references(chunk),
            "hash": generate_record_hash(parent_record, chunk, i),
            "ingested_at": parent_record['ingested_at'],
            "source": parent_record['source'],
            "chunk_meta": {
                "chunk_no": i,
                "chunk_count": len(chunks),
                "char_span": [0, len(chunk)],  # Relative to chunk content
                "est_tokens": tokenize_len(chunk)
            }
        }
        
        # Add semantic content field if semantic_path_string exists
        if parent_record.get('semantic_path_string'):
            child_record['semantic_content'] = f"{parent_record['semantic_path_string']} | {chunk}"
        child_records.append(child_record)
    
    return [parent_record] + child_records


def calculate_chunk_confidence(chunk: str) -> float:
    """
    Calculate confidence for a chunk based on various factors.
    Base: 0.7, with adjustments for quality indicators.
    """
    confidence = 0.7
    
    # +0.1 if begins with list marker
    if re.match(r'^[A-Z]\.|^[0-9]+\.|^[•\-–*]', chunk.strip()):
        confidence += 0.1
    
    # +0.1 if contains known heading vocabulary
    heading_vocabulary = [
        "shall", "must", "required", "prohibited", "permitted", "approved",
        "director", "department", "city", "code", "manual", "criteria"
    ]
    chunk_lower = chunk.lower()
    if any(vocab in chunk_lower for vocab in heading_vocabulary):
        confidence += 0.1
    
    # -0.1 if very short or mostly symbols
    if len(chunk.strip()) < 40 or len(re.findall(r'[^\w\s]', chunk)) > len(chunk) * 0.3:
        confidence -= 0.1
    
    # Cap between 0 and 1
    return max(0.0, min(1.0, confidence))


def extract_chunk_references(chunk: str) -> List[Dict[str, Any]]:
    """
    Extract references from chunk content using regex patterns.
    """
    refs = []
    
    # Pattern for Section references (Section 25-8-365)
    section_pattern = r'Section\s+(\d+-\d+-\d+)'
    for match in re.finditer(section_pattern, chunk):
        refs.append({
            "text": f"Section {match.group(1)}",
            "span": [match.start(), match.end()],
            "type": "CODE"
        })
    
    # Pattern for LDC references (LDC 25-8-186)
    ldc_pattern = r'LDC\s+(\d+-\d+-\d+)'
    for match in re.finditer(ldc_pattern, chunk):
        refs.append({
            "text": f"LDC {match.group(1)}",
            "span": [match.start(), match.end()],
            "type": "CODE"
        })
    
    # Pattern for Title references (Title 25-8)
    title_pattern = r'Title\s+(\d+-\d+)'
    for match in re.finditer(title_pattern, chunk):
        refs.append({
            "text": f"Title {match.group(1)}",
            "span": [match.start(), match.end()],
            "type": "CODE"
        })
    
    return refs


def generate_record_hash(record: Dict[str, Any], content: str, chunk_no: int) -> str:
    """
    Generate SHA-256 hash for a record, excluding the hash field itself.
    """
    # Create a copy without the hash field
    record_copy = record.copy()
    record_copy['content'] = content
    record_copy['chunk_no'] = chunk_no
    
    # Remove hash field if present
    if 'hash' in record_copy:
        del record_copy['hash']
    
    # Create stable concatenation
    parts = [
        str(record_copy.get('doc_id', '')),
        str(record_copy.get('anchor', '')),
        str(record_copy.get('title', '')),
        str(record_copy.get('subtitle', '')),
        str(record_copy.get('content', '')),
        str(chunk_no)
    ]
    concatenated = "|".join(parts)
    
    # Generate hash
    hash_obj = hashlib.sha256(concatenated.encode('utf-8'))
    return f"sha256:{hash_obj.hexdigest()}"


def process_jsonl_with_chunking(input_file: str, output_file: str, max_tokens: int = 300) -> None:
    """
    Process a JSONL file and apply hierarchical chunking to long content.
    """
    chunked_records = []
    
    with open(input_file, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            try:
                record = json.loads(line.strip())
                
                # Check if content needs chunking
                content = record.get('content', '')
                if content and tokenize_len(content) > max_tokens:
                    # Apply chunking
                    chunks = chunk_content(content, max_len=max_tokens)
                    chunked = make_chunk_records(record, chunks)
                    chunked_records.extend(chunked)
                else:
                    # No chunking needed, just update token count
                    record['tokens'] = tokenize_len(content) if content else 0
                    chunked_records.append(record)
                    
            except json.JSONDecodeError as e:
                print(f"Error parsing line {line_num}: {e}")
                continue
    
    # Write chunked records
    with open(output_file, 'w', encoding='utf-8') as f:
        for record in chunked_records:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')
    
    print(f"Processed {len(chunked_records)} records (including chunks)")
    print(f"Output written to: {output_file}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        print("Usage: python chunker.py <input.jsonl> <output.jsonl>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    process_jsonl_with_chunking(input_file, output_file) 