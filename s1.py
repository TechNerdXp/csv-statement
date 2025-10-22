import PyPDF2
import pdfplumber
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
PDF_DIRECTORY = r"PDFs22"  # Testing from C:\HSBC convert

# Output directory for CSV files
# Examples:
#   - OUTPUT_DIRECTORY = "csvs"                    # Project csvs folder (relative)
#   - OUTPUT_DIRECTORY = PDF_DIRECTORY             # Same as PDF location
#   - OUTPUT_DIRECTORY = r"C:\HSBC convert\CSVs"   # Absolute Windows path
OUTPUT_DIRECTORY = r"CSVs"  # Separate CSV output folder

# Output mode: Set to True for single combined CSV, False for separate CSV per PDF
# Examples:
#   - COMBINED_OUTPUT = False  # Default: Creates 2022-04-19_Statement_transactions.csv, etc.
#   - COMBINED_OUTPUT = True   # Creates single All_Transactions_YYYY-MM-DD_to_YYYY-MM-DD.csv
COMBINED_OUTPUT = True  # False = separate CSV for each PDF, True = one combined CSV
# ============================================================================

def extract_pdf_text(pdf_path):
    """Extract text from PDF file page by page"""
    with open(pdf_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)
        print(f"📄 Total pages in PDF: {len(pdf_reader.pages)}")
        all_text = []
        failed_pages = []
        
        for page_num, page in enumerate(pdf_reader.pages, 1):
            try:
                text = page.extract_text()
                all_text.append(text)
            except Exception as e:
                print(f"⚠️  Warning: PyPDF2 failed on page {page_num}: {str(e)}")
                failed_pages.append(page_num - 1)  # Store 0-indexed page number
                all_text.append("")  # Add empty string temporarily
        
        # If there are failed pages, try using pdfplumber
        if failed_pages:
            print(f"   📋 Attempting to extract {len(failed_pages)} failed page(s) using pdfplumber...")
            try:
                with pdfplumber.open(pdf_path) as pdf:
                    for page_idx in failed_pages:
                        try:
                            page = pdf.pages[page_idx]
                            text = page.extract_text()
                            if text:
                                all_text[page_idx] = text
                                print(f"   ✅ Successfully extracted page {page_idx + 1} using pdfplumber")
                            else:
                                print(f"   ⚠️  Page {page_idx + 1} has no extractable text")
                        except Exception as e:
                            print(f"   ❌ pdfplumber also failed on page {page_idx + 1}: {str(e)}")
            except Exception as e:
                print(f"   ❌ Could not open PDF with pdfplumber: {str(e)}")
        
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
    # Remove DR prefix from "DRNon-Sterling Transaction Fee"
    desc = re.sub(r'^DR(Non-Sterling Transaction Fee)', r'\1', desc)
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
    
    # First, collect all transaction lines (skip BALANCEBROUGHTFORWARD, stop at BALANCECARRIEDFORWARD footer)
    for line in lines:
        # Skip the opening BALANCEBROUGHTFORWARD line (start of statement)
        if 'BALANCEBROUGHTFORWARD' in line and 'BALANCECARRIEDFORWARD' not in line:
            continue
        # Stop when we hit the footer section (BALANCECARRIEDFORWARD, interest rates, etc.)
        if 'BALANCECARRIEDFORWARD' in line:
            break
        if 'Date Paymenttypeanddetails' in line:
            break
        # Stop at interest rate section markers
        if ('Creditinterest' in line and '%' in line) or ('upto 25' in line and '%' in line):
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
            # First, check for exchange rates (@ X.XXXX) and exclude them from amount detection
            line_without_rates = re.sub(r'@\s*[\d,]+\.\d+', '@', line)  # Replace rate with just @ symbol
            amounts = re.findall(r'[\d,]+\.\d{2}', line_without_rates)
            
            if amounts:
                # This line has the amounts - complete the transaction
                # Use original line for description (keep @ symbol for filtering later)
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
                    # One amount - could be trans_amt OR balance
                    # If description is empty/minimal, it's likely just a balance line
                    if not full_desc or len(full_desc) < 3:
                        trans_amt = ''
                        balance = clean_amount(amounts[0])
                    else:
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
    
    # INTERNATIONAL TRANSACTION PASS: Merge INT'L transactions with their Visa Rate lines
    # INT'L transactions are followed by a "Visa Rate" line showing the GBP equivalent
    # We need to use the Visa Rate amount as the actual transaction amount
    i = 0
    while i < len(transactions):
        trans = transactions[i]
        if "INT'L" in trans['description'] or 'International' in trans['description']:
            # Look for the next transaction on same date with "Visa Rate" in description
            if i + 1 < len(transactions):
                next_trans = transactions[i + 1]
                if next_trans['date'] == trans['date'] and 'Visa Rate' in next_trans['description']:
                    # Merge: use Visa Rate amount as the actual GBP amount
                    gbp_amount = next_trans['amount']
                    trans['amount'] = gbp_amount
                    # Remove the Visa Rate line
                    transactions.pop(i + 1)
                    print(f"  🔗 Merged INT'L transaction: {trans['description'][:40]} - GBP amount: £{gbp_amount}")
        i += 1
    
    # FINAL PASS: Look for orphaned transactions (no date, but have reference + amount)
    # These might be related charges that got separated in PDF extraction
    # Example: "DRNWBDM2I70822757 \n RBC08042JE908KCG 5.00" with no date
    # We'll match by reference code and insert after the related transaction
    # Search in ALL lines (not just transaction_lines), as orphans may be in footer section
    
    orphans_to_insert = []  # List of (index_to_insert_after, orphan_transaction)
    
    for idx in range(len(lines)):
        line = lines[idx].strip()
        # Skip if line has a date
        if re.match(r'^\d{2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{2}', line):
            continue
        # Skip if no amount
        if not re.search(r'[\d,]+\.\d{2}', line):
            continue
        # Skip if it's just a balance line or common text
        if 'BALANCE' in line or 'Date Payment' in line:
            continue
            
        # Look for reference codes (e.g., RBC08042JE908KCG)
        ref_match = re.search(r'[A-Z]{3}\d{5}[A-Z]{2}\d{3}[A-Z]{3}', line)
        if ref_match:
            reference = ref_match.group()
            amounts = re.findall(r'[\d,]+\.\d{2}', line)
            if amounts:
                orphan_amount = clean_amount(amounts[-1])
                # Try to find a transaction with matching reference and its index
                # We want to insert AFTER the balance-only line (not after the description line)
                # because they will be merged later
                for trans_idx, trans in enumerate(transactions):
                    if reference in trans['description']:
                        print(f"  🔗 Found orphaned transaction matching {reference}: £{orphan_amount}")
                        # Create a new transaction with same date and reference
                        desc_parts = line.replace(reference, '').strip()
                        for amt in amounts:
                            desc_parts = desc_parts.replace(amt, '').strip()
                        
                        # Find the balance-only line with same date (this is what will be merged)
                        orphan_balance = ''
                        balance_line_idx = trans_idx
                        for t_idx, t in enumerate(transactions):
                            if t['date'] == trans['date'] and not t['description'] and not t['amount'] and t['balance']:
                                orphan_balance = t['balance']
                                balance_line_idx = t_idx  # Insert after this line instead
                                break
                        
                        orphan_trans = {
                            'date': trans['date'],
                            'description': desc_parts + ' ' + reference if desc_parts else '',
                            'amount': orphan_amount,
                            'balance': orphan_balance,  # Use balance from balance-only line if found
                            '_is_orphan_debit': True  # Mark as orphaned debit for direction logic
                        }
                        orphans_to_insert.append((balance_line_idx, orphan_trans))  # Insert after balance line
                        print(f"  ✓ {trans['date']} | {(desc_parts + ' ' + reference if desc_parts else '')[:35]:<35} | £{orphan_amount:<10} | Bal: £{orphan_balance}")
                        break
    
    # Insert orphans in reverse order (so indices don't shift)
    for insert_idx, orphan_trans in reversed(orphans_to_insert):
        transactions.insert(insert_idx + 1, orphan_trans)
    
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
        
        # Strategy: Find desc-only transaction with same date that's closest to this balance line
        bal_date = bal_trans.get('date', '')
        
        # Find desc-only transactions with matching date
        candidates = [(desc_idx, desc_trans) for desc_idx, desc_trans in desc_only_trans 
                      if desc_trans.get('date') == bal_date and desc_idx not in skip_indices]
        
        if candidates:
            # Find the closest one (prefer the one right after the balance line)
            # Sort by absolute distance from bal_idx
            candidates.sort(key=lambda x: abs(x[0] - bal_idx))
            desc_idx, desc_trans = candidates[0]
            
            # Merge them - replace balance line with merged version
            merged_trans = {
                'date': bal_trans['date'],  # Use date from balance line
                'description': desc_trans['description'],
                'amount': desc_trans['amount'],
                'balance': bal_trans['balance']
            }
            replacements[bal_idx] = merged_trans
            skip_indices.add(desc_idx)
            print(f"  ✓ Merged: {bal_trans['date']} {desc_trans['description'][:30]} £{desc_trans['amount']} Bal:£{bal_trans['balance']}")
    
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
        
        # Determine IN/OUT based on transaction prefix codes from PDF
        desc = trans['description']
        
        # PAID IN (Credits to account):
        # - CR*/CRADVICE/CRA = Credits (always incoming)
        if desc.startswith(('CR', 'CRA', 'CRADVICE')):
            trans['paid_in'] = trans['amount']
            trans['paid_out'] = ''
        
        # BP = Bank Payment (can be incoming OR outgoing)
        # ESMER V D TAKA is incoming (person sending money)
        # Other BP are usually outgoing (paying invoices, etc.)
        elif desc.startswith('BP'):
            # Check if it's a known incoming BP pattern
            if 'ESMER V D TAKA' in desc.upper():
                trans['paid_in'] = trans['amount']
                trans['paid_out'] = ''
            elif current_balance is not None and previous_balance is not None:
                # Use balance change to determine
                if current_balance < previous_balance:
                    # Balance decreased = money out
                    trans['paid_out'] = trans['amount']
                    trans['paid_in'] = ''
                else:
                    # Balance increased = money in
                    trans['paid_in'] = trans['amount']
                    trans['paid_out'] = ''
            else:
                # No balance info - default to paid out for BP (most common)
                trans['paid_out'] = trans['amount']
                trans['paid_in'] = ''
        
        # PAID OUT (Debits from account):
        # - DD = Direct Debit
        # - VIS = Visa Card
        # - ATM = ATM withdrawal
        # - ))) = Contactless payment
        # - DR = Debit/Fee
        # Note: TFR (Transfer) removed - can be in OR out, needs balance check
        elif desc.startswith(('DD', 'VIS', 'ATM', ')))', 'DR')):
            trans['paid_out'] = trans['amount']
            trans['paid_in'] = ''
        
        # TFR = Transfer (can be incoming OR outgoing - check balance)
        elif desc.startswith('TFR'):
            if current_balance is not None and previous_balance is not None:
                if current_balance < previous_balance:
                    # Balance decreased = money out
                    trans['paid_out'] = trans['amount']
                    trans['paid_in'] = ''
                else:
                    # Balance increased = money in
                    trans['paid_in'] = trans['amount']
                    trans['paid_out'] = ''
            else:
                # No balance info - default to paid in for transfers
                trans['paid_in'] = trans['amount']
                trans['paid_out'] = ''
            trans['paid_in'] = ''
        
        # Empty description (orphaned transactions) - usually debits
        elif not desc or len(desc) < 3:
            # Check if marked as orphan debit
            if trans.get('_is_orphan_debit'):
                trans['paid_out'] = trans['amount']
                trans['paid_in'] = ''
            elif current_balance is not None and previous_balance is not None:
                if current_balance < previous_balance:
                    trans['paid_out'] = trans['amount']
                    trans['paid_in'] = ''
                else:
                    trans['paid_in'] = trans['amount']
                    trans['paid_out'] = ''
            else:
                # No balance info - default to paid out
                trans['paid_out'] = trans['amount']
                trans['paid_in'] = ''
        
        # Other/Unknown - use balance change if available
        else:
            if current_balance is not None and previous_balance is not None:
                if current_balance < previous_balance:
                    trans['paid_out'] = trans['amount']
                    trans['paid_in'] = ''
                else:
                    trans['paid_in'] = trans['amount']
                    trans['paid_out'] = ''
            else:
                # Default to paid out for unknown types
                trans['paid_out'] = trans['amount']
                trans['paid_in'] = ''
        
        # Update previous balance for next iteration
        if current_balance is not None:
            previous_balance = current_balance
    
    return all_transactions

def export_to_csv(transactions, output_file='statement_transactions.csv'):
    """Export transactions to CSV with all 6 required fields"""
    print(f"\n💾 Exporting to {output_file}...")
    
    # Filter out duplicate and unwanted entries
    filtered_transactions = []
    excluded_count = 0
    visa_rate_count = 0
    
    for trans in transactions:
        clean_desc = clean_description(trans['description'])
        
        # Skip "Fee for maintaining the account Monthly" as it's a duplicate of DRINS ASPECTS FEE
        if "Fee for maintaining the account Monthly" in clean_desc:
            excluded_count += 1
            print(f"  ⏭️  Excluding duplicate fee: {trans['date']} | {clean_desc}")
            continue
        
        # Skip "Visa Rate" entries - these are just exchange rate info lines, not actual transactions
        if "Visa Rate" in clean_desc:
            visa_rate_count += 1
            print(f"  ⏭️  Excluding Visa Rate info line: {trans['date']} | {clean_desc}")
            continue
        
        filtered_transactions.append(trans)
    
    if excluded_count > 0:
        print(f"  ℹ️  Excluded {excluded_count} duplicate bank fee transaction(s)")
    if visa_rate_count > 0:
        print(f"  ℹ️  Excluded {visa_rate_count} Visa Rate info line(s)")
    
    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['Date', 'Payment type', 'Details', '£Paid out', '£Paid in', '£Balance']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        for trans in filtered_transactions:
            payment_type = extract_payment_type(trans['description'])
            clean_desc = clean_description(trans['description'])
            
            writer.writerow({
                'Date': trans['date'].replace(' ', '-'),  # Convert "21 Mar 22" to "21-Mar-22"
                'Payment type': payment_type,
                'Details': clean_desc,
                '£Paid out': trans.get('paid_out', ''),
                '£Paid in': trans.get('paid_in', ''),
                '£Balance': trans['balance']
            })
    
    print(f"✅ Successfully exported {len(filtered_transactions)} transactions to {output_file}")
    return output_file

def process_pdf(pdf_path, output_dir, export=True):
    """
    Process a single PDF file and create CSV output.
    
    Args:
        pdf_path: Path to the PDF file
        output_dir: Directory for CSV output
        export: If True, export to CSV immediately. If False, return transactions for later export.
    """
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
    
    # Merge split transactions (only if exporting individually, not in combined mode)
    if export:
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
    
    # Export to CSV or return transactions
    if export:
        # Export to CSV with filename based on PDF name
        pdf_basename = os.path.splitext(os.path.basename(pdf_path))[0]
        output_filename = f"{pdf_basename}_transactions.csv"
        output_path = os.path.join(output_dir, output_filename)
        csv_file = export_to_csv(all_transactions, output_file=output_path)
        
        print("\n" + "="*70)
        print(f"🎉 DONE! Your transactions are in {csv_file}")
        print("="*70)
    else:
        # Return transactions for combined export
        return all_transactions
    
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
    
    print(f"\n📋 Mode: {'Combined output (one CSV for all PDFs)' if COMBINED_OUTPUT else 'Separate output (one CSV per PDF)'}")
    
    # Process based on mode
    if COMBINED_OUTPUT:
        # Combined mode: Collect all transactions first, then export once
        all_combined_transactions = []
        processed_count = 0
        
        for pdf_path in pdf_files:
            try:
                transactions = process_pdf(str(pdf_path), str(output_dir), export=False)
                all_combined_transactions.extend(transactions)
                processed_count += 1
            except Exception as e:
                print(f"\n❌ ERROR processing {pdf_path.name}: {str(e)}")
                import traceback
                traceback.print_exc()
                continue
        
        if all_combined_transactions:
            # Sort all transactions by date
            print("\n" + "="*70)
            print(f"📋 Combining and sorting {len(all_combined_transactions)} transactions...")
            print("="*70)
            
            # Convert date format from "21 Mar 22" to sortable format for proper ordering
            def parse_transaction_date(date_str):
                """Convert '21 Mar 22' to datetime-sortable format"""
                months = {
                    'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04',
                    'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08',
                    'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
                }
                parts = date_str.split()
                if len(parts) == 3:
                    day, month_name, year = parts
                    month = months.get(month_name, '00')
                    full_year = f"20{year}"  # Assume 20xx for years
                    return f"{full_year}{month}{day.zfill(2)}"  # YYYYMMDD format for sorting
                return date_str
            
            # Keep PDF's original order - don't sort by date
            # (Transactions are already in chronological order as they appear in the PDFs)
            print(f"✅ Keeping original PDF order for {len(all_combined_transactions)} transactions")
            
            # Merge split transactions
            print("\n📋 Merging split transactions...")
            all_combined_transactions = merge_split_transactions(all_combined_transactions)
            print(f"✅ After merging: {len(all_combined_transactions)} transactions")
            
            # Re-calculate working balances and direction after merging
            print("\n📋 Recalculating balances for debit/credit determination...")
            working_balances = calculate_working_balances(all_combined_transactions)
            all_combined_transactions = determine_debit_credit(all_combined_transactions, working_balances)
            
            # Fill in missing balances by propagating from known balances
            print("\n📋 Filling in missing balances...")
            for i in range(len(all_combined_transactions)):
                trans = all_combined_transactions[i]
                # If this transaction already has a balance, use it
                if trans.get('balance'):
                    continue
                
                # Find the previous transaction with a balance
                prev_balance = None
                for j in range(i-1, -1, -1):
                    if all_combined_transactions[j].get('balance'):
                        try:
                            prev_balance = float(all_combined_transactions[j]['balance'])
                            break
                        except:
                            pass
                
                # If we found a previous balance, calculate this transaction's balance
                if prev_balance is not None:
                    try:
                        paid_out = float(trans.get('paid_out', 0) or 0)
                        paid_in = float(trans.get('paid_in', 0) or 0)
                        new_balance = prev_balance - paid_out + paid_in
                        trans['balance'] = f"{new_balance:.2f}"
                        print(f"  ✓ Calculated balance for {trans['date']} {trans['description'][:30]}: £{new_balance:.2f}")
                    except Exception as e:
                        print(f"  ⚠️  Could not calculate balance for {trans['date']}: {e}")
            
            # Get date range from first and last transactions
            first_date = all_combined_transactions[0]['date']
            last_date = all_combined_transactions[-1]['date']
            first_sortable = parse_transaction_date(first_date)
            last_sortable = parse_transaction_date(last_date)
            
            # Format for filename: YYYY-MM-DD
            first_formatted = f"{first_sortable[:4]}-{first_sortable[4:6]}-{first_sortable[6:8]}"
            last_formatted = f"{last_sortable[:4]}-{last_sortable[4:6]}-{last_sortable[6:8]}"
            
            # Create combined CSV filename
            output_filename = f"All_Transactions_{first_formatted}_to_{last_formatted}.csv"
            output_path = os.path.join(str(output_dir), output_filename)
            
            csv_file = export_to_csv(all_combined_transactions, output_file=output_path)
            
            print("\n" + "="*70)
            print(f"🎉 DONE! Combined {len(all_combined_transactions)} transactions in {csv_file}")
            print("="*70)
    else:
        # Separate mode: Export each PDF individually
        processed_count = 0
        for pdf_path in pdf_files:
            try:
                process_pdf(str(pdf_path), str(output_dir), export=True)
                processed_count += 1
            except Exception as e:
                print(f"\n❌ ERROR processing {pdf_path.name}: {str(e)}")
                import traceback
                traceback.print_exc()
                continue
    
    print("\n" + "="*70)
    print(f"🎉 COMPLETE! Successfully processed {processed_count} of {len(pdf_files)} PDF file(s)")
    print("="*70)
