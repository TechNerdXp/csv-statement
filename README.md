# HSBC Statement to CSV Converter

**Turn your HSBC PDF statements into Excel-ready CSV files in seconds**

---

## 🎯 What You Get

Drop in your HSBC statement PDFs → Get clean CSV files with:
- ✅ Every transaction extracted
- ✅ Correct money IN vs OUT classification  
- ✅ Ready to open in Excel
- ✅ No data loss, no manual copying

---

## ⚡ Quick Start (3 Steps)

### 1️⃣ Put PDFs Here
```
pdfs/
└── 2024-04-30_Statement.pdf  ← Drop your HSBC statement here
```

### 2️⃣ Run This
```bash
py s1.py
```

### 3️⃣ Get Your CSV
```
csvs/
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

Open `s1.py`, change line 14:

```python
PDF_DIRECTORY = r"C:\HSBC convert"      # Your folder here
```

**Examples:**
```python
# Desktop folder
PDF_DIRECTORY = r"C:\Users\YourName\Desktop\Statements"

# Same folder for PDFs and CSVs
PDF_DIRECTORY = r"C:\Bank Files"
OUTPUT_DIRECTORY = PDF_DIRECTORY
```

---

## 🔥 Pro Tips

### Multiple PDFs? No Problem!
Put all your statements in `pdfs/` and run once:
```
pdfs/
├── 2024-03-31_Statement.pdf
├── 2024-04-30_Statement.pdf  
└── 2024-05-31_Statement.pdf

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
- Check PDFs are in the `pdfs/` folder
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
Hatem Statement Extractor/
├── s1.py          ← The magic happens here (single file!)
├── README.md      ← You are here
├── pdfs/          ← Drop PDFs here
├── csvs/          ← CSVs appear here
└── dox/           ← Guides and docs
    └── GUIDE.md   ← Full documentation
```

---

## 🚀 Requirements

- Python 3.x (probably already installed)
- PyPDF2 library (already set up in this project)

**That's literally it!** No database, no server, no account needed.

---

**Made with ❤️ by @TechNerdXp for easy bank statement processing**  
*Last updated: October 12, 2025*
