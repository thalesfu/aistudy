import json, subprocess
import pikepdf
from pikepdf import OutlineItem

pdf_in  = "out1.pdf"
json_in = "output.json"
pdf_out = "out2.pdf"

N = int(subprocess.check_output(["qpdf","--show-npages",pdf_in]).decode().strip())
data = json.load(open(json_in, "r", encoding="utf-8"))

def clamp_page1(p):
    if not isinstance(p, int): return 1
    if p < 1: return 1
    if p > N: return N
    return p

def add_items(parent_list, items):
    for b in items:
        title = b.get("title") or ""
        p1 = clamp_page1(b.get("page"))
        p0 = p1 - 1  # pikepdf 要 0-based page number
        oi = OutlineItem(title, p0, "Fit")   # 也可用 "FitH"
        parent_list.append(oi)
        kids = b.get("kids") or []
        if kids:
            add_items(oi.children, kids)

with pikepdf.Pdf.open(pdf_in) as pdf:
    with pdf.open_outline(strict=False) as outline:
        outline.root.clear()
        add_items(outline.root, data.get("bookmarks", []))
    pdf.save(pdf_out)

print("Wrote:", pdf_out)