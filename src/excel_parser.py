"""
Excel parser for ingesting structured Excel files and converting to JSON/Parquet.
"""

import re
import hashlib
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
from pathlib import Path

import pandas as pd
import regex as re
from loguru import logger

from .models import ExcelRow, Reference, Source, SectionLabels, ExcelIngestionConfig


class ExcelParser:
    """Parser for Excel files with structured data."""
    
    def __init__(self, config: ExcelIngestionConfig):
        """Initialize the Excel parser."""
        self.config = config
        self.heading_vocabulary = config.heading_vocabulary
        
        # Initialize context tracking for hierarchy
        self.current_context = {
            'section': None,
            'subsection': None,
            'subsubsection': None
        }
        
        # Compile regex patterns for reference detection
        self.ref_patterns = {
            'section': re.compile(r'\b(?:Section|Sec\.|§)\s*\d{1,2}-\d-\d+(?:\([A-Za-z0-9]+\))*'),
            'ldc': re.compile(r'\bLDC\s*\d{1,2}-\d-\d+(?:\([A-Za-z0-9]+\))*'),
            'title': re.compile(r'\bTitle\s*\d+-\d+'),
        }
        
        # Glossary cues for block type detection
        self.glossary_cues = [
            "is defined as", "means", "refers to", "shall mean",
            "Definitions", "Glossary", "Terms", "Definitions and Terms"
        ]
    
    def parse_excel_file(self, file_path: str) -> List[ExcelRow]:
        """
        Parse an Excel file and convert to structured records.
        
        Args:
            file_path: Path to the Excel file
            
        Returns:
            List of ExcelRow objects
        """
        logger.info(f"Parsing Excel file: {file_path}")
        
        try:
            # Read Excel file - use second row as headers (first row is empty)
            df = pd.read_excel(file_path, sheet_name=0, header=1)  # Use second row as headers
            
            # Validate required columns
            required_columns = ['NodeId']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                raise ValueError(f"Missing required columns: {missing_columns}")
            
            # Process each row
            rows = []
            for index, row_data in df.iterrows():
                try:
                    excel_row = self._process_row(row_data, index)
                    if excel_row:
                        rows.append(excel_row)
                except Exception as e:
                    logger.warning(f"Error processing row {index}: {e}")
                    continue
            
            logger.info(f"Successfully processed {len(rows)} rows")
            return rows
            
        except Exception as e:
            logger.error(f"Error parsing Excel file: {e}")
            raise
    
    def _process_row(self, row_data: pd.Series, index: int) -> Optional[ExcelRow]:
        """Process a single row and convert to ExcelRow."""
        # Extract basic fields
        original_node_id = str(row_data.get('NodeId', '')).strip()
        title = str(row_data.get('Title', '')).strip() if pd.notna(row_data.get('Title')) else None
        subtitle = str(row_data.get('Subtitle', '')).strip() if pd.notna(row_data.get('Subtitle')) else None
        content = str(row_data.get('Content', '')).strip() if pd.notna(row_data.get('Content')) else None
        url = str(row_data.get('Url', '')).strip() if pd.notna(row_data.get('Url')) else None
        
        # Skip rows without title
        if not title:
            return None
        
        # Generate title-based identifiers
        node_id = self._generate_title_based_node_id(title)
        anchor = self._generate_title_based_anchor(title)
        
        # Use context-based hierarchy determination
        path, parent_anchor = self._determine_hierarchy_from_context(title, self.current_context)
        
        # Determine block type
        block_type = self._determine_block_type(title, content)
        
        # Generate section labels
        section_labels = self._generate_section_labels(path)
        
        # Calculate order
        order = self._calculate_order(node_id)
        
        # Calculate confidence
        confidence = self._calculate_confidence(title, content)
        
        # Extract references
        refs = self._extract_references(content) if content else []
        
        # Generate hash
        content_hash = self._generate_hash(node_id, title, subtitle, content)
        
        # Create ExcelRow
        excel_row = ExcelRow(
            doc_id=self.config.doc_id,
            anchor=anchor,
            node_id=node_id,
            title=title,
            subtitle=subtitle,
            content=content,
            url=url,
            path=path,
            parent_anchor=parent_anchor,
            block_type=block_type,
            section_labels=section_labels,
            order=order,
            tokens=0,  # Placeholder
            confidence=confidence,
            refs=refs,
            hash=content_hash,
            ingested_at=datetime.utcnow().isoformat(),
            source=Source(type="excel", file="AustinTXEnvironmentalCriteriaManualEXPORT20250102.xlsx")
        )
        
        return excel_row
    
    def _generate_title_based_anchor(self, title: str) -> str:
        """Generate anchor based on title structure."""
        if not title:
            return "untitled"
        
        # Check if title follows numeric pattern (e.g., "1.1.0", "1.2.1.1")
        if re.match(r'^\d+(\.\d+)*$', title.strip()):
            return title.strip()
        
        # For non-numeric titles, create a slug
        # Remove special characters and convert to lowercase
        anchor = re.sub(r'[^\w\s-]', '', title.lower())
        anchor = re.sub(r'[-\s]+', '-', anchor)
        anchor = anchor.strip('-')
        
        return anchor if anchor else "untitled"
    
    def _generate_title_based_node_id(self, title: str) -> str:
        """Generate node_id based on title structure."""
        if not title:
            return "untitled"
        
        # Check if title follows numeric pattern (e.g., "1.1.0", "1.2.1.1")
        if re.match(r'^\d+(\.\d+)*$', title.strip()):
            return title.strip()
        
        # For non-numeric titles, create a slug
        anchor = re.sub(r'[^\w\s-]', '', title.lower())
        anchor = re.sub(r'[-\s]+', '-', anchor)
        anchor = anchor.strip('-')
        
        return anchor if anchor else "untitled"
    
    def _determine_hierarchy_from_context(self, title: str, current_context: dict) -> tuple:
        """Determine hierarchy based on current context and title."""
        if not re.match(r'^\d+(\.\d+)*$', title.strip()):
            return [self._generate_title_based_anchor(title)], None
        
        parts = title.strip().split('.')
        
        if len(parts) == 1:  # e.g., "1" - top level section
            current_context['section'] = title
            current_context['subsection'] = None
            current_context['subsubsection'] = None
            # Return section name like "SECTION 1"
            section_name = f"SECTION {title}"
            return [self._generate_title_based_anchor(section_name)], None
        
        elif len(parts) == 2:  # e.g., "1.2" - major subsection (if it exists)
            if parts[0] != current_context.get('section'):
                current_context['section'] = parts[0]
            current_context['subsection'] = title
            current_context['subsubsection'] = None
            # Return path: ["SECTION 1", "1.2"] - only the actual title
            section_name = f"SECTION {current_context['section']}"
            return [self._generate_title_based_anchor(section_name), title], self._generate_title_based_anchor(section_name)
        
        elif len(parts) == 3:  # e.g., "1.2.0" or "1.2.1" - check if it ends with .0
            if parts[0] != current_context.get('section'):
                current_context['section'] = parts[0]
            
            # Check if it ends with .0 (major subsection) or not (minor subsection)
            if parts[2] == '0':  # e.g., "1.2.0" - major subsection
                current_context['subsection'] = title
                current_context['subsubsection'] = None
                # Return path: ["SECTION 1", "1.2.0"] - only the actual title
                section_name = f"SECTION {current_context['section']}"
                return [self._generate_title_based_anchor(section_name), title], self._generate_title_based_anchor(section_name)
            else:  # e.g., "1.2.1" - minor subsection
                # Find the parent subsection (e.g., "1.2.0" for "1.2.1")
                parent_subsection = '.'.join(parts[:2]) + '.0'
                current_context['subsection'] = parent_subsection
                current_context['subsubsection'] = title
                # Return path: ["SECTION 1", "1.2.0", "1.2.1"] - only actual titles
                section_name = f"SECTION {current_context['section']}"
                return [self._generate_title_based_anchor(section_name), parent_subsection, title], parent_subsection
        
        elif len(parts) == 4:  # e.g., "1.2.1.1" - detail level
            if parts[0] != current_context.get('section'):
                current_context['section'] = parts[0]
            # Find the parent subsection (e.g., "1.2.0" for "1.2.1")
            parent_subsection = '.'.join(parts[:2]) + '.0'
            # Find the parent subsubsection (e.g., "1.2.1" for "1.2.1.1")
            parent_subsubsection = '.'.join(parts[:3])
            current_context['subsection'] = parent_subsection
            current_context['subsubsection'] = parent_subsubsection
            # Return path: ["SECTION 1", "1.2.0", "1.2.1", "1.2.1.1"] - only actual titles
            section_name = f"SECTION {current_context['section']}"
            return [self._generate_title_based_anchor(section_name), parent_subsection, parent_subsubsection, title], parent_subsubsection
        
        elif len(parts) == 4:  # e.g., "1.2.1.1" - detail level
            if parts[0] != current_context.get('section'):
                current_context['section'] = parts[0]
            # Find the parent subsection (e.g., "1.2.0" for "1.2.1")
            parent_subsection = '.'.join(parts[:2]) + '.0'
            # Find the parent subsubsection (e.g., "1.2.1" for "1.2.1.1")
            parent_subsubsection = '.'.join(parts[:3])
            current_context['subsection'] = parent_subsection
            current_context['subsubsection'] = parent_subsubsection
            # Return path: ["SECTION 1", "1.2.0", "1.2.1", "1.2.1.1"] - only actual titles
            section_name = f"SECTION {current_context['section']}"
            return [self._generate_title_based_anchor(section_name), parent_subsection, parent_subsubsection, title], parent_subsubsection
        
        return [title], None
    
    def _generate_title_based_path(self, title: str) -> List[str]:
        """Generate path based on title structure."""
        if not title:
            return ["untitled"]
        
        # Check if title follows numeric pattern (e.g., "1.1.0", "1.2.1.1")
        if re.match(r'^\d+(\.\d+)*$', title.strip()):
            parts = title.strip().split('.')
            
            # For numeric titles, we need to find the section they belong to
            # and build the path based on the actual hierarchy
            section_number = parts[0]  # e.g., "1" from "1.1.0"
            section_title = f"SECTION {section_number}"
            section_anchor = self._generate_title_based_anchor(section_title)
            
            # Build path starting with the section
            path = [section_anchor]
            
            # For multi-level numeric titles, add each level
            if len(parts) >= 2:
                # Add the major subsection (e.g., "1.1" from "1.1.0")
                major_subsection = '.'.join(parts[:2])
                path.append(major_subsection)
                
                # Add the full title if it has more parts
                if len(parts) > 2:
                    path.append(title.strip())
            else:
                # Single level numeric title
                path.append(title.strip())
            
            return path
        
        # For non-numeric titles, they're all at the same top level
        return [self._generate_title_based_anchor(title)]
    
    def _get_title_based_parent_anchor(self, title: str) -> Optional[str]:
        """Get parent anchor based on title structure."""
        if not title:
            return None
        
        # Check if title follows numeric pattern (e.g., "1.1.0", "1.2.1.1")
        if re.match(r'^\d+(\.\d+)*$', title.strip()):
            parts = title.strip().split('.')
            
            # For numeric titles, the parent depends on the level
            if len(parts) == 1:  # e.g., "1" -> no parent (top level section)
                return None
            elif len(parts) == 2:  # e.g., "1.1" -> parent is "SECTION 1"
                section_number = parts[0]
                section_title = f"SECTION {section_number}"
                return self._generate_title_based_anchor(section_title)
            elif len(parts) >= 3:  # e.g., "1.1.1" -> parent is "1.1"
                # Find the immediate parent by removing the last part
                parent_parts = parts[:-1]
                return '.'.join(parent_parts)
            
            return None
        
        # For non-numeric titles, no parent (top level)
        return None
    
    def _normalize_anchor(self, node_id: str) -> str:
        """Normalize anchor by removing trailing .0 if configured."""
        if self.config.normalize_anchors and node_id.endswith('.0'):
            return node_id[:-2]  # Remove trailing .0
        return node_id
    
    def _generate_path(self, node_id: str) -> List[str]:
        """Generate cumulative path segments from NodeId."""
        parts = node_id.split('.')
        path = []
        current = ""
        
        for part in parts:
            if current:
                current += "." + part
            else:
                current = part
            path.append(current)
        
        return path
    
    def _get_parent_anchor(self, node_id: str) -> Optional[str]:
        """Get parent anchor (everything before the last dot)."""
        if '.' in node_id:
            return node_id.rsplit('.', 1)[0]
        return None
    
    def _determine_block_type(self, title: Optional[str], content: Optional[str]) -> str:
        """Determine block type based on content."""
        # Check for glossary cues
        if title:
            title_lower = title.lower()
            if any(cue.lower() in title_lower for cue in self.glossary_cues):
                return "GLOSSARY"
        
        if content:
            content_lower = content.lower()
            if any(cue.lower() in content_lower for cue in self.glossary_cues):
                return "GLOSSARY"
            
            # Check for table markup (simplified)
            if '|' in content and content.count('|') > 2:
                return "TABLE"
        
        # Check for heading vs paragraph
        if title and not content:
            return "HEADING"
        elif title and content:
            return "HEADING"  # Heading with content
        elif content and not title:
            return "PARA"
        else:
            return "PARA"  # Default
    
    def _generate_section_labels(self, path: List[str]) -> SectionLabels:
        """Generate section labels based on path depth."""
        labels = SectionLabels()
        
        if len(path) >= 1:
            labels.section = path[0]
        if len(path) >= 2:
            labels.chapter = path[1]
        if len(path) >= 3:
            labels.subsection = path[2]
        
        return labels
    
    def _calculate_order(self, node_id: str) -> int:
        """Convert NodeId to sortable integer order."""
        # Handle text-based NodeIds by using hash for ordering
        if not node_id.replace('.', '').replace('_', '').isdigit():
            # For text NodeIds, use a hash-based approach
            return hash(node_id) % 1000000  # Use modulo to keep it reasonable
        
        # Original logic for numeric NodeIds
        parts = node_id.split('.')
        padded_parts = []
        
        for part in parts:
            # Remove trailing .0 if present
            if part.endswith('.0'):
                part = part[:-2]
            # Pad to 3 digits
            padded_parts.append(part.zfill(3))
        
        # Join and convert to integer
        order_str = ''.join(padded_parts)
        return int(order_str)
    
    def _calculate_confidence(self, title: Optional[str], content: Optional[str]) -> float:
        """Calculate confidence score."""
        confidence = 0.9  # Base confidence
        
        # Penalty for empty content
        if not title and not content:
            confidence -= 0.1
        
        # Boost for known heading vocabulary
        if title:
            title_lower = title.lower()
            for vocab in self.heading_vocabulary:
                if vocab.lower() in title_lower:
                    confidence += 0.05
                    break
        
        # Clamp to [0, 1]
        return max(0.0, min(1.0, confidence))
    
    def _extract_references(self, content: str) -> List[Reference]:
        """Extract code references from content."""
        refs = []
        
        for ref_type, pattern in self.ref_patterns.items():
            for match in pattern.finditer(content):
                ref = Reference(
                    text=match.group(0),
                    span=[match.start(), match.end()],
                    type="CODE"
                )
                refs.append(ref)
        
        return refs
    
    def _generate_hash(self, node_id: str, title: Optional[str], 
                      subtitle: Optional[str], content: Optional[str]) -> str:
        """Generate SHA-256 hash over stable concatenation."""
        # Create stable concatenation
        parts = [
            node_id,
            title or "",
            subtitle or "",
            content or ""
        ]
        concatenated = "|".join(parts)
        
        # Generate hash
        hash_obj = hashlib.sha256(concatenated.encode('utf-8'))
        return f"sha256:{hash_obj.hexdigest()}"
    
    def write_output(self, rows: List[ExcelRow], output_prefix: str):
        """Write output in specified format."""
        if self.config.output_format in ["jsonl", "both"]:
            self._write_jsonl(rows, f"{output_prefix}.jsonl")
        
        if self.config.output_format in ["parquet", "both"]:
            self._write_parquet(rows, f"{output_prefix}.parquet")
    
    def _write_jsonl(self, rows: List[ExcelRow], output_file: str):
        """Write rows to JSONL format."""
        logger.info(f"Writing JSONL output to: {output_file}")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            for row in rows:
                f.write(row.json() + '\n')
        
        logger.info(f"Successfully wrote {len(rows)} rows to JSONL")
    
    def _write_parquet(self, rows: List[ExcelRow], output_file: str):
        """Write rows to Parquet format."""
        logger.info(f"Writing Parquet output to: {output_file}")
        
        # Convert to DataFrame
        data = []
        for row in rows:
            row_dict = row.dict()
            # Flatten section_labels
            row_dict['section'] = row_dict['section_labels']['section']
            row_dict['chapter'] = row_dict['section_labels']['chapter']
            row_dict['subsection'] = row_dict['section_labels']['subsection']
            del row_dict['section_labels']
            data.append(row_dict)
        
        df = pd.DataFrame(data)
        df.to_parquet(output_file, index=False)
        
        logger.info(f"Successfully wrote {len(rows)} rows to Parquet") 