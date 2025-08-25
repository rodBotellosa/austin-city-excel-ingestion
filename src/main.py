"""
Main CLI entry point for the Austin City Excel Ingestion Tool.
"""

import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from loguru import logger

from .excel_parser import ExcelParser
from .models import ExcelIngestionConfig

# Initialize Typer app
app = typer.Typer(
    name="austin-excel-ingestion",
    help="Austin City Excel Ingestion Tool",
    add_completion=False
)

# Initialize Rich console
console = Console()


@app.command()
def ingest(
    file_path: str = typer.Argument(..., help="Path to Excel file"),
    output_prefix: str = typer.Option(None, "--output", "-o", help="Output file prefix"),
    doc_id: str = typer.Option("ecm", "--doc-id", "-d", help="Document ID"),
    output_format: str = typer.Option("both", "--format", "-f", help="Output format: jsonl, parquet, or both"),
    normalize_anchors: bool = typer.Option(True, "--normalize-anchors", help="Remove trailing .0 from anchors"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging")
):
    """
    Ingest an Excel file and convert to structured JSON/Parquet format.
    """
    try:
        # Configure logging
        log_level = "DEBUG" if verbose else "INFO"
        logger.remove()
        logger.add(sys.stderr, level=log_level)
        
        # Validate input file
        if not Path(file_path).exists():
            console.print(f"[red]Error: File {file_path} does not exist.[/red]")
            raise typer.Exit(1)
        
        # Set output prefix if not provided
        if not output_prefix:
            output_prefix = Path(file_path).stem
        
        # Create configuration
        config = ExcelIngestionConfig(
            doc_id=doc_id,
            output_format=output_format,
            normalize_anchors=normalize_anchors
        )
        
        console.print(f"[green]Starting ingestion of Excel file: {file_path}[/green]")
        console.print(f"Document ID: {doc_id}")
        console.print(f"Output format: {output_format}")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            # Initialize parser
            task = progress.add_task("Initializing parser...", total=None)
            parser = ExcelParser(config)
            progress.update(task, description="Parser initialized")
            
            # Parse Excel file
            task = progress.add_task("Parsing Excel file...", total=None)
            rows = parser.parse_excel_file(file_path)
            progress.update(task, description=f"Parsed {len(rows)} rows")
            
            # Write output
            task = progress.add_task("Writing output files...", total=None)
            parser.write_output(rows, output_prefix)
            progress.update(task, description="Output files written")
        
        # Print summary
        console.print(f"\n[green]Successfully processed {len(rows)} rows[/green]")
        
        # Show output files
        if output_format in ["jsonl", "both"]:
            jsonl_file = f"{output_prefix}.jsonl"
            if Path(jsonl_file).exists():
                console.print(f"JSONL output: {jsonl_file}")
        
        if output_format in ["parquet", "both"]:
            parquet_file = f"{output_prefix}.parquet"
            if Path(parquet_file).exists():
                console.print(f"Parquet output: {parquet_file}")
        
        # Show statistics
        if rows:
            _show_statistics(rows)
        
    except Exception as e:
        logger.error(f"Error during ingestion: {e}")
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def validate(
    file_path: str = typer.Argument(..., help="Path to Excel file"),
    detailed: bool = typer.Option(False, "--detailed", "-d", help="Show detailed validation")
):
    """
    Validate an Excel file structure without processing.
    """
    try:
        import pandas as pd
        
        console.print(f"[cyan]Validating Excel file: {file_path}[/cyan]")
        
        # Read Excel file
        df = pd.read_excel(file_path, sheet_name=0)
        
        # Check required columns
        required_columns = ['NodeId']
        optional_columns = ['Title', 'Subtitle', 'Content', 'Url']
        
        console.print(f"\n[cyan]File Structure:[/cyan]")
        console.print(f"  Total rows: {len(df)}")
        console.print(f"  Total columns: {len(df.columns)}")
        
        # Check required columns
        missing_required = [col for col in required_columns if col not in df.columns]
        if missing_required:
            console.print(f"[red]Missing required columns: {missing_required}[/red]")
            raise typer.Exit(1)
        else:
            console.print(f"[green]✓ All required columns present[/green]")
        
        # Check optional columns
        present_optional = [col for col in optional_columns if col in df.columns]
        console.print(f"  Optional columns present: {present_optional}")
        
        # Show column info
        if detailed:
            console.print(f"\n[cyan]Column Details:[/cyan]")
            for col in df.columns:
                non_null_count = df[col].notna().sum()
                console.print(f"  {col}: {non_null_count}/{len(df)} non-null values")
        
        # Validate NodeId format
        if 'NodeId' in df.columns:
            node_ids = df['NodeId'].dropna()
            console.print(f"\n[cyan]NodeId Analysis:[/cyan]")
            console.print(f"  Non-null NodeIds: {len(node_ids)}")
            
            # Check for common patterns
            patterns = {
                'with_trailing_zero': node_ids.astype(str).str.endswith('.0').sum(),
                'numeric_only': node_ids.astype(str).str.match(r'^\d+(\.\d+)*$').sum(),
                'max_depth': max([len(str(id).split('.')) for id in node_ids]) if len(node_ids) > 0 else 0
            }
            
            console.print(f"  With trailing .0: {patterns['with_trailing_zero']}")
            console.print(f"  Numeric format: {patterns['numeric_only']}")
            console.print(f"  Maximum depth: {patterns['max_depth']}")
        
        console.print(f"\n[green]✓ File validation completed successfully[/green]")
        
    except Exception as e:
        console.print(f"[red]Validation failed: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def preview(
    file_path: str = typer.Argument(..., help="Path to Excel file"),
    rows: int = typer.Option(5, "--rows", "-r", help="Number of rows to preview")
):
    """
    Preview Excel file structure and sample data.
    """
    try:
        import pandas as pd
        
        console.print(f"[cyan]Previewing Excel file: {file_path}[/cyan]")
        
        # Read Excel file - use second row as headers (first row is empty)
        df = pd.read_excel(file_path, sheet_name=0, header=1)
        
        # Show basic info
        console.print(f"\n[cyan]File Information:[/cyan]")
        console.print(f"  Shape: {df.shape[0]} rows × {df.shape[1]} columns")
        console.print(f"  Columns: {list(df.columns)}")
        
        # Show sample data
        console.print(f"\n[cyan]Sample Data (first {rows} rows):[/cyan]")
        
        # Create table
        table = Table(title=f"Preview of {file_path}")
        for col in df.columns:
            table.add_column(col, style="cyan")
        
        # Add sample rows
        for i, row in df.head(rows).iterrows():
            table.add_row(*[str(val) if pd.notna(val) else "" for val in row])
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]Preview failed: {e}[/red]")
        raise typer.Exit(1)


def _show_statistics(rows):
    """Show processing statistics."""
    console.print(f"\n[cyan]Processing Statistics:[/cyan]")
    
    # Block type distribution
    block_types = {}
    for row in rows:
        block_type = row.block_type
        block_types[block_type] = block_types.get(block_type, 0) + 1
    
    console.print(f"  Block type distribution:")
    for block_type, count in sorted(block_types.items()):
        percentage = (count / len(rows)) * 100
        console.print(f"    {block_type}: {count} ({percentage:.1f}%)")
    
    # Confidence distribution
    high_conf = len([r for r in rows if r.confidence >= 0.8])
    medium_conf = len([r for r in rows if 0.6 <= r.confidence < 0.8])
    low_conf = len([r for r in rows if r.confidence < 0.6])
    
    console.print(f"  Confidence distribution:")
    console.print(f"    High (≥0.8): {high_conf} ({high_conf/len(rows)*100:.1f}%)")
    console.print(f"    Medium (0.6-0.8): {medium_conf} ({medium_conf/len(rows)*100:.1f}%)")
    console.print(f"    Low (<0.6): {low_conf} ({low_conf/len(rows)*100:.1f}%)")
    
    # Reference statistics
    total_refs = sum(len(row.refs) for row in rows)
    rows_with_refs = len([r for r in rows if r.refs])
    
    console.print(f"  References:")
    console.print(f"    Total references: {total_refs}")
    console.print(f"    Rows with references: {rows_with_refs} ({rows_with_refs/len(rows)*100:.1f}%)")


if __name__ == "__main__":
    app() 