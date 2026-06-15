#!/usr/bin/env python3
"""
Debug script to test Visa XLSX parser with a specific file.
"""

import pandas as pd
from pathlib import Path
from app.importers.visa_xlsx import parse_visa_xlsx, _detect_statement_year_month

def debug_visa_file(file_path: str):
    """Debug the parsing of a Visa XLSX file."""
    path = Path(file_path)
    if not path.exists():
        print(f"File not found: {file_path}")
        return
    
    print(f"Debugging file: {file_path}")
    print("=" * 50)
    
    # Read raw Excel to see structure
    print("Raw Excel structure:")
    df_raw = pd.read_excel(path, sheet_name=0, header=None)
    print(f"Shape: {df_raw.shape}")
    print("First 10 rows:")
    for i in range(min(10, len(df_raw))):
        row = df_raw.iloc[i].astype(str).tolist()
        print(f"  Row {i}: {row[:8]}...")  # Show first 8 columns
    
    print("\n" + "=" * 50)
    
    # Try to detect statement year_month
    statement_ym = _detect_statement_year_month(df_raw)
    print(f"Detected statement year_month: {statement_ym}")
    
    # Try to find header row
    header_row_idx = None
    for i in range(len(df_raw)):
        row = df_raw.iloc[i].astype(str).tolist()
        if any("descripción" in c.lower() for c in row) and any("monto en pesos" in c.lower() for c in row):
            header_row_idx = i
            print(f"Found header row at index: {i}")
            print(f"Header row: {row}")
            break
    
    if header_row_idx is None:
        print("Could not find header row!")
        return
    
    # Show the parsed data
    print("\n" + "=" * 50)
    print("Parsing with parse_visa_xlsx...")
    
    try:
        parsed = parse_visa_xlsx(path)
        print(f"Successfully parsed {len(parsed)} rows")
        
        for i, row in enumerate(parsed[:5]):  # Show first 5 rows
            print(f"  Row {i+1}: {row}")
            
        if len(parsed) > 5:
            print(f"  ... and {len(parsed) - 5} more rows")
            
    except Exception as e:
        print(f"Error parsing: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python debug_visa_parser.py <path_to_xlsx>")
        sys.exit(1)
    
    debug_visa_file(sys.argv[1])
