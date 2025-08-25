"""
Data models for Excel ingestion.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, validator
import hashlib


class Reference(BaseModel):
    """Reference information for code citations."""
    text: str = Field(..., description="Reference text")
    span: List[int] = Field(..., description="Character span [start, end]")
    type: str = Field(..., description="Reference type (CODE, URL, etc.)")


class Source(BaseModel):
    """Source information."""
    type: str = Field(..., description="Source type (excel)")
    file: str = Field(..., description="Source filename")


class SectionLabels(BaseModel):
    """Section labels based on hierarchy depth."""
    section: Optional[str] = Field(None, description="Depth 1 label")
    chapter: Optional[str] = Field(None, description="Depth 2 label")
    subsection: Optional[str] = Field(None, description="Depth 3 label")


class ExcelRow(BaseModel):
    """Canonical block record for each Excel row."""
    doc_id: str = Field(..., description="Constant collection ID")
    anchor: str = Field(..., description="Normalized NodeId (strip trailing .0)")
    node_id: str = Field(..., description="Original NodeId as-is")
    title: Optional[str] = Field(None, description="Section/heading title")
    subtitle: Optional[str] = Field(None, description="Subheading/caption")
    content: Optional[str] = Field(None, description="Body text for the node")
    url: Optional[str] = Field(None, description="Web source URL")
    path: List[str] = Field(..., description="Cumulative path segments")
    parent_anchor: Optional[str] = Field(None, description="Parent anchor")
    block_type: str = Field(..., description="Block type (HEADING|PARA|TABLE|APPENDIX|GLOSSARY)")
    section_labels: SectionLabels = Field(..., description="Section labels")
    order: int = Field(..., description="Sortable integer order")
    tokens: int = Field(0, description="Token count (placeholder)")
    confidence: float = Field(..., description="Confidence score")
    refs: List[Reference] = Field(default_factory=list, description="References found")
    hash: str = Field(..., description="SHA-256 hash")
    ingested_at: str = Field(..., description="ISO-8601 timestamp")
    source: Source = Field(..., description="Source information")

    @validator('confidence')
    def validate_confidence(cls, v):
        """Ensure confidence is between 0 and 1."""
        return max(0.0, min(1.0, v))

    @validator('hash')
    def validate_hash(cls, v):
        """Ensure hash starts with sha256:."""
        if not v.startswith('sha256:'):
            return f"sha256:{v}"
        return v

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }


class ExcelIngestionConfig(BaseModel):
    """Configuration for Excel ingestion."""
    doc_id: str = Field("ecm", description="Document ID")
    heading_vocabulary: List[str] = Field(
        default=[
            "Operating Permit", "Environmental Resource Inventory", 
            "Interbasin Diversion", "Pollution Attenuation", 
            "Resource Extraction", "Administrative", "General", 
            "Definitions", "Glossary", "Appendix"
        ],
        description="Known heading vocabulary for confidence scoring"
    )
    output_format: str = Field("both", description="Output format: jsonl, parquet, or both")
    normalize_anchors: bool = Field(True, description="Remove trailing .0 from anchors") 