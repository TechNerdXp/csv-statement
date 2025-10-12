# 🏦 HSBC Statement to CSV Converter

**Turn your HSBC PDF statements into Excel-ready CSV files in seconds**

> **📦 EXTRACT LOCATION:** `C:\HSBC convert\`  
> **📄 Quick Start?** → Read `QUICK_START.txt` first!

---

## 🎯 What You Get

Drop in your HSBC statement PDFs → Get clean CSV files with:
- ✅ Every transaction extracted
- ✅ Correct money IN vs OUT classification  
- ✅ Ready to open in Excel
- ✅ No data loss, no manual copying

---

## ⚡ Quick Start (4 Steps)

### 1️⃣ Install Dependencies (First Time Only)
```bash
cd "C:\HSBC convert"
pip install -r requirements.txt
```

### 2️⃣ Put PDFs Here
```
C:\HSBC convert\
└── 2024-04-30_Statement.pdf  ← Drop your HSBC statement here
```

### 3️⃣ Run This
```bash
cd "C:\HSBC convert"
py s1.py
```

### 4️⃣ Get Your CSV
```
C:\HSBC convert\CSVs\
└── 2024-04-30_Statement_transactions.csv  ← Opens in Excel!
```

**That's it!** Double-click the CSV to open in Excel.

---

## 📊 Your CSV Will Have

| Date | Payment type | Details | £Paid out | £Paid in | £Balance |
|------|-------------|---------|-----------|----------|----------|
| 02 Apr 24 | Direct Debit | EDF ENERGY | 136.75 | | 3751.06 |
| 26 Apr 24 | Credit | A Fancsali KOSZI | | 350.00 | 1388.96 |
| 30 Apr 24 | Visa Card | STARBUCKS | 10.95 | | 4816.30 |

Perfect for:
- 💰 Budget tracking in Excel
- 📈 Expense analysis
- 🧾 Accounting software import
- 📋 Record keeping

---

## 💡 Need Different Folders?

**Default configuration (already set for you):**
```python
PDF_DIRECTORY = r"PDFs"      # Looks in C:\HSBC convert\PDFs\
OUTPUT_DIRECTORY = r"CSVs"   # Outputs to C:\HSBC convert\CSVs\
```

**To change:** Open `s1.py`, find lines 17-23, and modify:

**Examples:**
```python
# Put PDFs directly in C:\HSBC convert\
PDF_DIRECTORY = r"C:\HSBC convert"
OUTPUT_DIRECTORY = r"C:\HSBC convert\CSVs"

# Use different location
PDF_DIRECTORY = r"C:\Users\YourName\Desktop\Statements"
OUTPUT_DIRECTORY = r"C:\Users\YourName\Desktop\Statements\CSVs"

# Relative paths (inside C:\HSBC convert\)
PDF_DIRECTORY = "pdfs"
OUTPUT_DIRECTORY = "csvs"
```

---

## 🔥 Pro Tips

### Multiple PDFs? No Problem!
Put all your statements in `C:\HSBC convert\PDFs\` and run once:
```
C:\HSBC convert\PDFs\
├── 2024-03-31_Statement.pdf
├── 2024-04-30_Statement.pdf  
└── 2024-05-31_Statement.pdf

cd "C:\HSBC convert"
py s1.py → Converts all 3 at once!
```

### Already Have Excel Open?
Close the CSV file before running the script again, or you'll get an error.

### Want to Verify?
The script shows you exactly what it found:
- ✅ Found 56 transactions
- Sample preview of first 5 transactions
- File location printed at the end

---

## ❓ Troubleshooting

**"No PDF files found"**
- Check PDFs are in the `C:\HSBC convert\PDFs\` folder
- Make sure filenames end with `.pdf`

**"PermissionError"**
- Close the CSV file in Excel
- Try running as administrator

**"Wrong amounts"**
- This script uses smart balance-based detection
- Should be 100% accurate for HSBC UK statements
- If not, let us know - it's a bug!

**Need more help?** See `dox/GUIDE.md` for detailed guide.

---

## 🏦 Works With

✅ **HSBC UK Personal Bank Statements** (PDF format)  
❌ Other banks - they use different formats  
❌ Scanned PDFs - must be digital PDF (test: can you select text with mouse?)

---

## 📦 What's Inside

```
C:\HSBC convert\
├── s1.py                  ← The converter script (single file!)
├── requirements.txt       ← Required library list
├── QUICK_START.txt        ← Quick command reference
├── README.md              ← You are here
├── PDFs\                  ← Drop your HSBC PDFs here
├── CSVs\                  ← Converted CSVs appear here (auto-created)
└── dox\                   ← Additional documentation
    ├── GUIDE.md           ← Comprehensive user manual
    └── ADVANCED.md        ← Technical customization guide
```

---

## 🚀 Requirements

- **Python 3.x** (Download from https://python.org if needed)
- **PyPDF2 library** (Install with: `pip install -r requirements.txt`)

**That's literally it!** No database, no server, no account needed.

---

**Made with ❤️ by @TechNerdXp for easy bank statement processing**  
*Last updated: October 13, 2025*
