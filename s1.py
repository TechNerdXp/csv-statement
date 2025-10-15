import PyPDF2
import re
import csv
import os
import sys
from pathlib import Path

# Fix Unicode encoding for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# ============================================================================
# CONFIGURATION - Define PDF location here
# ============================================================================
# Set the directory where your HSBC PDF statements are located
# Examples:
#   - PDF_DIRECTORY = "pdfs"                                    # Project pdfs folder (relative)
#   - PDF_DIRECTORY = r"C:\HSBC convert"                        # Absolute Windows path
#   - PDF_DIRECTORY = r"C:\Users\YourName\Documents\Statements" # Another absolute path
PDF_DIRECTORY = r"PDFs"  # Testing from C:\HSBC convert

# Output directory for CSV files
# Examples:
#   - OUTPUT_DIRECTORY = "csvs"                    # Project csvs folder (relative)
#   - OUTPUT_DIRECTORY = PDF_DIRECTORY             # Same as PDF location
#   - OUTPUT_DIRECTORY = r"C:\HSBC convert\CSVs"   # Absolute Windows path
OUTPUT_DIRECTORY = r"CSVs"  # Separate CSV output folder
# ============================================================================

def extract_pdf_text(pdf_path):
    """Extract text from PDF file page by page"""
    with open(pdf_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)
        print(f"📄 Total pages in PDF: {len(pdf_reader.pages)}")
        all_text = []
        for page in pdf_reader.pages:
            text = page.extract_text()
            all_text.append(text)
        return all_text

def clean_amount(amount_str):
    """Clean amount string by removing commas"""
    return amount_str.replace(',', '')

def extract_payment_type(description):
    """Extract payment type from description"""
    payment_types = {
        'DD': 'Direct Debit',
        'VISA': 'Visa Card',
        'VIS': 'Visa Card',
        'BP': 'Bank Payment',
        'CR': 'Credit',
        ')))': 'Contactless',
        'CRS': 'Credit Transfer',
        'CRA': 'Credit Transfer'
    }
    
    for code, full_name in payment_types.items():
        if description.startswith(code):
            return full_name
    
    return 'Other'

def clean_description(desc):
    """Clean up description by removing payment type codes and extra spaces"""
    # Remove payment type prefixes
    desc = re.sub(r'^(DD|VISA|VIS|BP|CR|CRS|CRA|\)\)\))', '', desc)
    # Remove multiple spaces
    desc = re.sub(r'\s+', ' ', desc)
    return desc.strip()

def parse_page_transactions(page_text, page_num, last_date_from_prev_page=None):
    """Parse transactions from a single page"""
    print(f"\n{'='*70}")
    print(f"PROCESSING PAGE {page_num}")
    print('='*70)
    
    # Skip info pages
    if 'Commercial Banking Customers' in page_text or 'Personal Banking Customers' in page_text:
        print("⏭️  Skipping info page...")
        return [], None
    
    transactions = []
    
    # Extract the transaction section
    # The section ends at "BALANCEBROUGHTFORWARD" or "Date Paymenttypeanddetails"
    # But some transactions are merged with these markers, so we need to extract them first
    
    # Replace merged markers to separate transactions
    page_text = re.sub(r'(\d+\.\d{2})(\d{2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{2})\s+BALANCE', r'\1\n\2 BALANCE', page_text)
    page_text = re.sub(r'(\d+\.\d{2})BALANCE', r'\1\nBALANCE', page_text)
    
    lines = page_text.split('\n')
    transaction_lines = []
    
    # First, collect all transaction lines (before BALANCEBROUGHTFORWARD/BALANCECARRIEDFORWARD footer)
    for line in lines:
        # Stop when we hit the footer section with both markers
        if 'BALANCEBROUGHTFORWARD' in line and 'BALANCECARRIEDFORWARD' in line:
            break
        if 'Date Paymenttypeanddetails' in line:
            break
        transaction_lines.append(line)
    
    # Parse transactions
    current_date = last_date_from_prev_page  # Start with last date from previous page
    current_desc_parts = []
    i = 0
    
    # Skip header/informational lines at the start (before first transaction)
    found_first_transaction = False
    
    while i < len(transaction_lines):
        line = transaction_lines[i].strip()
        
        if not line or 'BALANCE' in line:
            i += 1
            continue
        
        # Skip header lines (lines without payment codes or dates)
        if not found_first_transaction:
            # Check if this line starts a transaction (has date OR payment code)
            has_date = re.match(r'^(\d{2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{2})', line)
            has_payment_code = re.match(r'^(DD|VISA|VIS|BP|CR|CRS|CRA|\)\)\))', line)
            
            if not has_date and not has_payment_code:
                # Skip this header line
                i += 1
                continue
            else:
                found_first_transaction = True
        
        # Check for date at start of line
        date_match = re.match(r'^(\d{2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{2})\s+(.+)', line)
        
        if date_match:
            current_date = date_match.group(1)
            rest = date_match.group(2).strip()
            
            # Check if amounts are on this line
            amounts = re.findall(r'[\d,]+\.\d{2}', rest)
            
            if amounts:
                # Complete transaction on one line
                desc = rest
                for amt in amounts:
                    desc = desc.replace(amt, '').strip()
                
                if len(amounts) >= 2:
                    trans_amt = clean_amount(amounts[-2])
                    balance = clean_amount(amounts[-1])
                elif len(amounts) == 1:
                    # One amount - could be trans_amt OR balance
                    # If description is empty after removing amount, it's likely a balance-only line
                    if not desc or len(desc) < 3:
                        # Balance-only line (no description)
                        trans_amt = ''
                        balance = clean_amount(amounts[0])
                        desc = ''  # Explicitly empty
                    else:
                        # Normal transaction with amount but no balance
                        trans_amt = clean_amount(amounts[0])
                        balance = ''
                
                transactions.append({
                    'date': current_date,
                    'description': desc,
                    'amount': trans_amt,
                    'balance': balance
                })
                print(f"  ✓ {current_date} | {desc[:35]:<35} | £{trans_amt:<10} | Bal: £{balance}")
                current_desc_parts = []
            else:
                # Description starts, continues on next lines
                current_desc_parts = [rest]
        
        elif current_date:
            # Line without date - continuation or amount line
            amounts = re.findall(r'[\d,]+\.\d{2}', line)
            
            if amounts:
                # This line has the amounts - complete the transaction
                desc_part = line
                for amt in amounts:
                    desc_part = desc_part.replace(amt, '').strip()
                
                if desc_part:
                    current_desc_parts.append(desc_part)
                
                full_desc = ' '.join(current_desc_parts).strip()
                
                if len(amounts) >= 2:
                    trans_amt = clean_amount(amounts[-2])
                    balance = clean_amount(amounts[-1])
                elif len(amounts) == 1:
                    trans_amt = clean_amount(amounts[0])
                    balance = ''
                
                transactions.append({
                    'date': current_date,
                    'description': full_desc,
                    'amount': trans_amt,
                    'balance': balance
                })
                print(f"  ✓ {current_date} | {full_desc[:35]:<35} | £{trans_amt:<10} | Bal: £{balance}")
                current_desc_parts = []
            else:
                # No amounts yet, keep building description
                if line:
                    current_desc_parts.append(line)
        
        i += 1
    
    # Return transactions and the last date seen on this page
    return transactions, current_date

def merge_split_transactions(transactions):
    """Merge transactions that were split between page body and footer"""
    # Find transactions with only balance (date + balance, no description/amount)
    # Find transactions with description but no balance (from footer)
    # Match and merge them based on balance calculations
    
    # Create a map to track what should replace each index
    replacements = {}  # index -> new transaction dict
    skip_indices = set()  # indices to skip (merged away)
    
    balance_only_trans = []  # Transactions with date+balance but no description/amount
    desc_only_trans = []     # Transactions with description but suspicious date/no balance
    
    for i, trans in enumerate(transactions):
        desc = trans.get('description', '').strip()
        balance = trans.get('balance', '').strip()
        amount = trans.get('amount', '').strip()
        
        # Check if this is a balance-only line (no description, no amount, has balance)
        if not desc and not amount and balance:
            # This is a balance-only line - transaction details should be elsewhere
            balance_only_trans.append((i, trans))
        # Check if this is a description line from footer (has desc+amount, no balance)
        elif desc and amount and not balance:
            desc_only_trans.append((i, trans))
    
    # Try to match balance-only with desc-only transactions
    for bal_idx, bal_trans in balance_only_trans:
        if bal_idx in skip_indices:
            continue
            
        # Calculate what the transaction amount should be
        try:
            balance_val = float(bal_trans['balance'])
            # Find previous balance by looking at ORIGINAL transactions list before this one
            prev_balance = None
            for j in range(bal_idx - 1, -1, -1):
                if transactions[j].get('balance'):
                    try:
                        prev_balance = float(transactions[j]['balance'])
                        break
                    except:
                        pass
            
            if prev_balance:
                # Calculate expected transaction amount
                expected_amount = abs(prev_balance - balance_val)
                
                # Find matching desc-only transaction
                for desc_idx, desc_trans in desc_only_trans:
                    if desc_idx in skip_indices:
                        continue
                    try:
                        desc_amount = float(desc_trans['amount'])
                        if abs(desc_amount - expected_amount) < 0.5:  # Match found!
                            # Merge them - replace balance line with merged version
                            merged_trans = {
                                'date': bal_trans['date'],  # Use date from balance line
                                'description': desc_trans['description'],
                                'amount': desc_trans['amount'],
                                'balance': bal_trans['balance']
                            }
                            replacements[bal_idx] = merged_trans
                            skip_indices.add(desc_idx)  # Skip the desc-only line
                            print(f"  ✓ Merged: {bal_trans['date']} {desc_trans['description'][:30]} £{desc_trans['amount']} Bal:£{bal_trans['balance']}")
                            break
                    except:
                        pass
        except:
            pass
    
    # Build final list maintaining original order
    result = []
    for i, trans in enumerate(transactions):
        if i in skip_indices:
            continue  # This was merged into another transaction
        elif i in replacements:
            result.append(replacements[i])  # Use merged version
        else:
            result.append(trans)  # Keep original
    
    return result

def calculate_working_balances(transactions):
    """Calculate balances for internal use without modifying original transaction data"""
    # Create a parallel list with calculated balances for determining IN/OUT
    # but DON'T modify the original balance field (respect HSBC's formatting)
    
    working_balances = []  # Will store calculated balance for each transaction
    last_known_balance = None
    
    for i in range(len(transactions)):
        if transactions[i]['balance']:
            # This transaction has a balance from PDF - use it as anchor point
            current_bal = float(transactions[i]['balance'])
            working_balances.append(current_bal)
            last_known_balance = current_bal
        else:
            # No balance in PDF - need to calculate from previous
            if last_known_balance is None:
                # No previous balance known yet
                working_balances.append(None)
            else:
                # Calculate based on description and transaction type
                try:
                    amt = float(transactions[i]['amount'])
                except:
                    amt = 0
                
                desc = transactions[i]['description']
                # Credits (CR/CRS/CRA) add to balance, everything else subtracts
                if desc.startswith(('CR', 'CRS', 'CRA')):
                    # Money IN
                    last_known_balance += amt
                else:
                    # Money OUT (default)
                    last_known_balance -= amt
                
                working_balances.append(last_known_balance)
    
    return working_balances

def determine_debit_credit(all_transactions, working_balances=None):
    """Determine paid out vs paid in by analyzing balance changes"""
    # If no working balances provided, calculate them
    if working_balances is None:
        working_balances = calculate_working_balances(all_transactions)
    
    previous_balance = None
    
    for i, trans in enumerate(all_transactions):
        try:
            amount = float(trans['amount'])
        except:
            amount = 0
        
        # Use working balance for this transaction
        current_balance = working_balances[i]
        
        if current_balance is not None and previous_balance is not None:
            # Check if balance went UP or DOWN
            # Money OUT: current = previous - amount (balance decreased)
            # Money IN: current = previous + amount (balance increased)
            
            money_out_diff = abs(current_balance - (previous_balance - amount))
            money_in_diff = abs(current_balance - (previous_balance + amount))
            
            # Tolerance for fees/rounding
            if money_out_diff < 5:  # Money OUT (balance decreased)
                trans['paid_out'] = trans['amount']
                trans['paid_in'] = ''
            elif money_in_diff < 5:  # Money IN (balance increased)
                trans['paid_in'] = trans['amount']
                trans['paid_out'] = ''
            else:
                # Can't determine from balance - check if balance actually decreased or increased
                if current_balance < previous_balance:
                    trans['paid_out'] = trans['amount']
                    trans['paid_in'] = ''
                else:
                    trans['paid_in'] = trans['amount']
                    trans['paid_out'] = ''
        elif current_balance is not None:
            # First transaction with balance - need to guess
            # Check the account summary to know starting balance
            # For now, assume CR/CRS/CRA = IN, others = OUT
            desc = trans['description']
            if desc.startswith(('CR', 'CRS', 'CRA')):
                trans['paid_in'] = trans['amount']
                trans['paid_out'] = ''
            else:
                trans['paid_out'] = trans['amount']
                trans['paid_in'] = ''
        else:
            # No balance info - guess based on description
            desc = trans['description']
            if desc.startswith(('CR', 'CRS', 'CRA')):
                trans['paid_in'] = trans['amount']
                trans['paid_out'] = ''
            else:
                trans['paid_out'] = trans['amount']
                trans['paid_in'] = ''
        
        # Update previous balance for next iteration
        if current_balance is not None:
            previous_balance = current_balance
    
    return all_transactions

def export_to_csv(transactions, output_file='statement_transactions.csv'):
    """Export transactions to CSV with all 6 required fields"""
    print(f"\n💾 Exporting to {output_file}...")
    
    # Filter out duplicate "Fee for maintaining the account Monthly" entries
    # These are duplicates of "DRINS ASPECTS FEE" charges
    filtered_transactions = []
    excluded_count = 0
    
    for trans in transactions:
        clean_desc = clean_description(trans['description'])
        
        # Skip "Fee for maintaining the account Monthly" as it's a duplicate of DRINS ASPECTS FEE
        if "Fee for maintaining the account Monthly" in clean_desc:
            excluded_count += 1
            print(f"  ⏭️  Excluding duplicate fee: {trans['date']} | {clean_desc}")
            continue
        
        filtered_transactions.append(trans)
    
    if excluded_count > 0:
        print(f"  ℹ️  Excluded {excluded_count} duplicate bank fee transaction(s)")
    
    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['Date', 'Payment type', 'Details', '£Paid out', '£Paid in', '£Balance']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        for trans in filtered_transactions:
            payment_type = extract_payment_type(trans['description'])
            clean_desc = clean_description(trans['description'])
            
            writer.writerow({
                'Date': trans['date'],
                'Payment type': payment_type,
                'Details': clean_desc,
                '£Paid out': trans.get('paid_out', ''),
                '£Paid in': trans.get('paid_in', ''),
                '£Balance': trans['balance']
            })
    
    print(f"✅ Successfully exported {len(filtered_transactions)} transactions to {output_file}")
    return output_file

def process_pdf(pdf_path, output_dir):
    """Process a single PDF file and create CSV output"""
    print("\n" + "="*70)
    print(f"  Processing: {os.path.basename(pdf_path)}")
    print("="*70)
    
    print("\n📋 STEP 1: Reading PDF...")
    pages = extract_pdf_text(pdf_path)
    
    print("\n📋 STEP 2: Processing pages...")
    all_transactions = []
    last_date = None
    
    for page_num, page_text in enumerate(pages, 1):
        page_transactions, last_date = parse_page_transactions(page_text, page_num, last_date)
        all_transactions.extend(page_transactions)
    
    print("\n" + "="*70)
    print(f"✅ Found {len(all_transactions)} transactions across {len(pages)} pages")
    print("="*70)
    
    # Merge split transactions (e.g., balance line + description from footer)
    print("\n📋 Merging split transactions...")
    all_transactions = merge_split_transactions(all_transactions)
    print(f"✅ After merging: {len(all_transactions)} transactions")
    
    # Calculate working balances for determining IN/OUT (without modifying balance field)
    print("\n📋 Calculating balances for debit/credit determination...")
    working_balances = calculate_working_balances(all_transactions)
    
    print("\n📋 STEP 3: Determining debits vs credits...")
    all_transactions = determine_debit_credit(all_transactions, working_balances)
    
    # Show summary
    print("\n📊 Sample transactions (first 5):")
    for trans in all_transactions[:5]:
        payment_type = extract_payment_type(trans['description'])
        clean_desc = clean_description(trans['description'])
        paid_out = trans.get('paid_out', '')
        paid_in = trans.get('paid_in', '')
        print(f"  • {trans['date']} | {payment_type:15} | {clean_desc[:30]:<30} | Out:£{paid_out if paid_out else '-':<8} | In:£{paid_in if paid_in else '-':<8}")
    
    # Export to CSV with filename based on PDF name
    pdf_basename = os.path.splitext(os.path.basename(pdf_path))[0]
    output_filename = f"{pdf_basename}_transactions.csv"
    output_path = os.path.join(output_dir, output_filename)
    csv_file = export_to_csv(all_transactions, output_file=output_path)
    
    print("\n" + "="*70)
    print(f"🎉 DONE! Your transactions are in {csv_file}")
    print("="*70)
    
    return csv_file

if __name__ == "__main__":
    print("="*70)
    print("  HSBC BANK STATEMENT TO CSV CONVERTER")
    print("="*70)
    
    # Ensure directories exist (convert to absolute paths)
    pdf_dir = Path(PDF_DIRECTORY).resolve()
    output_dir = Path(OUTPUT_DIRECTORY).resolve()
    
    print(f"\n📂 PDF Directory: {pdf_dir}")
    print(f"📂 Output Directory: {output_dir}")
    
    # Create PDF directory if it doesn't exist
    try:
        if not pdf_dir.exists():
            print(f"   📁 Creating PDF directory...")
            pdf_dir.mkdir(parents=True, exist_ok=True)
            print(f"   ✅ PDF directory created successfully!")
        else:
            print(f"   ✅ PDF directory exists")
    except Exception as e:
        print(f"\n❌ ERROR: Cannot create PDF directory: {pdf_dir}")
        print(f"   Reason: {str(e)}")
        print(f"\n💡 Please check:")
        print(f"   - Directory path is valid")
        print(f"   - You have write permissions")
        print(f"   - Parent directories exist or can be created")
        exit(1)
    
    # Create output directory if it doesn't exist
    try:
        if not output_dir.exists():
            print(f"   📁 Creating output directory...")
            output_dir.mkdir(parents=True, exist_ok=True)
            print(f"   ✅ Output directory created successfully!")
        else:
            print(f"   ✅ Output directory exists")
    except Exception as e:
        print(f"\n❌ ERROR: Cannot create output directory: {output_dir}")
        print(f"   Reason: {str(e)}")
        print(f"\n💡 Please check:")
        print(f"   - Directory path is valid")
        print(f"   - You have write permissions")
        print(f"   - Parent directories exist or can be created")
        exit(1)
    
    # Find all PDF files in the specified directory
    pdf_files = list(pdf_dir.glob("*.pdf"))
    
    if not pdf_files:
        print(f"\n⚠️  No PDF files found in {pdf_dir}")
        print(f"\n💡 Next steps:")
        print(f"   1. Place your HSBC statement PDF(s) in: {pdf_dir}")
        print(f"   2. Run this script again")
        print(f"\n   Or update PDF_DIRECTORY at the top of this script (currently set to: '{PDF_DIRECTORY}')")
        exit(0)
    
    print(f"\n📄 Found {len(pdf_files)} PDF file(s) to process:")
    for pdf in pdf_files:
        print(f"   - {pdf.name}")
    
    # Process each PDF file
    processed_count = 0
    for pdf_path in pdf_files:
        try:
            process_pdf(str(pdf_path), str(output_dir))
            processed_count += 1
        except Exception as e:
            print(f"\n❌ ERROR processing {pdf_path.name}: {str(e)}")
            import traceback
            traceback.print_exc()
            continue
    
    print("\n" + "="*70)
    print(f"🎉 COMPLETE! Successfully processed {processed_count} of {len(pdf_files)} PDF file(s)")
    print("="*70)
