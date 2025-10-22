"""
Test script to compare generated CSV with known-correct CSV
Focuses on essential columns: Date, Payment type, Details, Paid out, Paid in, Balance
"""

import csv
from pathlib import Path

def normalize_date(date_str):
    """Normalize date format for comparison (remove leading zeros, handle dashes vs spaces)"""
    # Convert "21 Mar 22" to "21-Mar-22" format or vice versa
    date_str = date_str.strip()
    # Remove leading zeros from day
    parts = date_str.replace('-', ' ').split()
    if len(parts) == 3:
        day = str(int(parts[0]))  # Remove leading zero
        month = parts[1]
        year = parts[2]
        return f"{day}-{month}-{year}"
    return date_str

def normalize_amount(amount_str):
    """Normalize amount for comparison (handle decimals, empty values)"""
    amount_str = str(amount_str).strip()
    if not amount_str or amount_str == '':
        return ''
    try:
        # Convert to float and back to handle "100" vs "100.00"
        return f"{float(amount_str):.2f}"
    except:
        return amount_str

def compare_csvs(generated_file, known_correct_file):
    """Compare the two CSV files line by line"""
    
    print("=" * 80)
    print("  CSV COMPARISON TEST")
    print("=" * 80)
    print(f"Generated: {generated_file}")
    print(f"Known-Correct: {known_correct_file}")
    print()
    
    # Read both files
    with open(generated_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        generated = list(reader)
        gen_headers = reader.fieldnames
    
    with open(known_correct_file, 'r', encoding='utf-8-sig') as f:  # utf-8-sig to handle BOM
        reader = csv.DictReader(f)
        known_correct = list(reader)
        known_headers = reader.fieldnames
    
    # Create a mapping for column names (handle different encodings of £ symbol)
    def find_column(headers, search_terms):
        """Find column name that contains any of the search terms"""
        for term in search_terms:
            for h in headers:
                if term.lower() in h.lower():
                    return h
        return None
    
    gen_paid_out = find_column(gen_headers, ['paid out', 'paidout'])
    gen_paid_in = find_column(gen_headers, ['paid in', 'paidin'])
    gen_balance = find_column(gen_headers, ['balance'])
    
    known_paid_out = find_column(known_headers, ['paid out', 'paidout'])
    known_paid_in = find_column(known_headers, ['paid in', 'paidin'])
    known_balance = find_column(known_headers, ['balance', 'bal'])
    
    print(f"Column mapping:")
    print(f"   Generated: '{gen_paid_out}', '{gen_paid_in}', '{gen_balance}'")
    print(f"   Known-Correct: '{known_paid_out}', '{known_paid_in}', '{known_balance}'")
    print()
    
    print(f"Row counts:")
    print(f"   Generated: {len(generated)} transactions")
    print(f"   Known-Correct: {len(known_correct)} transactions")
    print()
    
    if len(generated) != len(known_correct):
        print(f"MISMATCH: Row count differs by {abs(len(generated) - len(known_correct))} rows")
        print()
    else:
        print("Row count matches!")
        print()
    
    # Compare row by row
    differences = []
    matches = 0
    
    max_rows = max(len(generated), len(known_correct))
    
    for i in range(max_rows):
        if i >= len(generated):
            differences.append({
                'row': i + 2,  # +2 for header and 1-indexed
                'issue': 'Missing in generated file',
                'known_correct': known_correct[i]
            })
            continue
        
        if i >= len(known_correct):
            differences.append({
                'row': i + 2,
                'issue': 'Extra row in generated file',
                'generated': generated[i]
            })
            continue
        
        gen = generated[i]
        known = known_correct[i]
        
        row_diffs = []
        
        # Compare Date
        gen_date = normalize_date(gen.get('Date', ''))
        known_date = normalize_date(known.get('Date', ''))
        if gen_date != known_date:
            row_diffs.append(f"Date: '{gen_date}' vs '{known_date}'")
        
        # Compare Payment type
        gen_type = gen.get('Payment type', '').strip()
        known_type = known.get('Payment type', '').strip()
        if gen_type != known_type:
            row_diffs.append(f"Type: '{gen_type}' vs '{known_type}'")
        
        # Compare Details
        gen_details = gen.get('Details', '').strip()
        known_details = known.get('Details', '').strip()
        if gen_details != known_details:
            row_diffs.append(f"Details: '{gen_details}' vs '{known_details}'")
        
        # Compare Paid out (use column name with £ symbol)
        gen_out = normalize_amount(gen.get(gen_paid_out, ''))
        known_out = normalize_amount(known.get(known_paid_out, ''))
        if gen_out != known_out:
            row_diffs.append(f"Paid out: '{gen_out}' vs '{known_out}'")
        
        # Compare Paid in
        gen_in = normalize_amount(gen.get(gen_paid_in, ''))
        known_in = normalize_amount(known.get(known_paid_in, ''))
        if gen_in != known_in:
            row_diffs.append(f"Paid in: '{gen_in}' vs '{known_in}'")
        
        # Compare Balance
        gen_bal = normalize_amount(gen.get(gen_balance, ''))
        known_bal = normalize_amount(known.get(known_balance, ''))
        if gen_bal != known_bal:
            row_diffs.append(f"Balance: '{gen_bal}' vs '{known_bal}'")
        
        if row_diffs:
            differences.append({
                'row': i + 2,
                'date': gen_date,
                'details': gen_details[:40],
                'diffs': row_diffs
            })
        else:
            matches += 1
    
    # Print summary
    print("=" * 80)
    print("  RESULTS")
    print("=" * 80)
    print(f"Matching rows: {matches}")
    print(f"Rows with differences: {len(differences)}")
    print()
    
    if differences:
        print("=" * 80)
        print("  DIFFERENCES FOUND")
        print("=" * 80)
        for diff in differences[:20]:  # Show first 20 differences
            print(f"\nRow {diff['row']}: {diff.get('date', 'N/A')} - {diff.get('details', 'N/A')[:40]}")
            if 'issue' in diff:
                print(f"  ⚠️  {diff['issue']}")
            else:
                for d in diff['diffs']:
                    print(f"  • {d}")
        
        if len(differences) > 20:
            print(f"\n... and {len(differences) - 20} more differences")
    
    print("\n" + "=" * 80)
    if len(differences) == 0:
        print("PERFECT MATCH! All rows identical!")
        return True
    else:
        print(f"Found {len(differences)} differences out of {max_rows} rows")
        print(f"   Accuracy: {matches}/{max_rows} = {100*matches/max_rows:.1f}%")
        
        # Categorize differences
        balance_only = sum(1 for d in differences if 'diffs' in d and len(d['diffs']) == 1 and 'Balance' in d['diffs'][0])
        print(f"   Balance-only differences: {balance_only}")
        print(f"   Other differences: {len(differences) - balance_only}")
        return False
    print("=" * 80)

if __name__ == '__main__':
    generated = Path('CSVs/All_Transactions_2022-03-21_to_2022-06-17.csv')
    known_correct = Path('known-correct-2.csv')
    
    if not generated.exists():
        print(f"Generated file not found: {generated}")
        exit(1)
    
    if not known_correct.exists():
        print(f"Known-correct file not found: {known_correct}")
        exit(1)
    
    success = compare_csvs(generated, known_correct)
    exit(0 if success else 1)
