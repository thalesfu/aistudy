#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import os
import shutil
import subprocess
import sys

try:
    import pikepdf
    from pikepdf import OutlineItem
except ImportError:
    print("缺少依赖：pikepdf。请先安装：python -m pip install pikepdf", file=sys.stderr)
    raise


def run(cmd: list[str]) -> None:
    """Run a command and raise on failure, printing stdout/stderr for debugging."""
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode != 0:
        print("Command failed:", " ".join(cmd), file=sys.stderr)
        if p.stdout:
            print("stdout:\n", p.stdout, file=sys.stderr)
        if p.stderr:
            print("stderr:\n", p.stderr, file=sys.stderr)
        raise RuntimeError(f"Command failed: {' '.join(cmd)}")


def shift_pages_to_previous_original(bookmarks, prev_original=1):
    """
    前序遍历：每个书签的 page 改成“前一个书签的原始 page”
    - 第一个书签的 page 改成 prev_original（默认 1）
    - 同层/跨层都按遍历顺序“串起来”
    """
    for bm in bookmarks:
        cur_original = bm.get("page")
        try:
            cur_original = int(cur_original)
        except (TypeError, ValueError):
            cur_original = prev_original

        bm["page"] = prev_original
        prev_original = cur_original

        kids = bm.get("kids")
        if isinstance(kids, list) and kids:
            prev_original = shift_pages_to_previous_original(kids, prev_original)

    return prev_original


def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(obj: dict, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def write_bookmarks_and_dup_first_page_to_end(pdf_in: str, bookmarks_json: str, pdf_out: str, dest_mode: str = "Fit") -> None:
    """
    1) 默认：复制第一页并追加到最后（必须从另一个 Pdf 实例复制，避免 duplicate page reference）
    2) 用 output.json 重建书签树（更兼容 UPDF/多看）
    """
    data = load_json(bookmarks_json)

    with pikepdf.Pdf.open(pdf_in) as pdf:
        # ✅ 默认流程：复制第一页到最后
        # 注意：不要用 pdf.pages.append(pdf.pages[0])，那是同一个页面引用，会触发 duplicate page reference。
        with pikepdf.Pdf.open(pdf_in) as pdf2:
            pdf.pages.append(pdf2.pages[0])

        N = len(pdf.pages)

        def clamp_page1(p):
            if not isinstance(p, int):
                return 1
            if p < 1:
                return 1
            if p > N:
                return N
            return p

        def add_items(parent_list, items):
            for b in items:
                title = b.get("title") or ""
                p1 = clamp_page1(b.get("page"))
                p0 = p1 - 1  # pikepdf 用 0-based 页码
                oi = OutlineItem(title, p0, dest_mode)  # "Fit" / "FitH" / "FitV"
                parent_list.append(oi)
                kids = b.get("kids") or []
                if kids:
                    add_items(oi.children, kids)

        with pdf.open_outline(strict=False) as outline:
            outline.root.clear()
            add_items(outline.root, data.get("bookmarks", []))

        pdf.save(pdf_out)


def main():
    ap = argparse.ArgumentParser(
        description="Fix calibre-generated PDF bookmarks (shift by one) and rewrite bookmarks for better reader compatibility. "
                    "Default: duplicate first page to end."
    )
    ap.add_argument("pdf", help="输入 PDF（例如 o.pdf）")
    ap.add_argument("--workdir", default=".", help="工作目录（默认当前目录）")
    ap.add_argument("--tmp-input-json", default="input.json", help="导出书签 JSON 文件名")
    ap.add_argument("--tmp-output-json", default="output.json", help="修正后书签 JSON 文件名")
    ap.add_argument("--out-no-bm", default="out1.pdf", help="删除原书签后的 PDF")
    ap.add_argument("--out", default="out2.pdf", help="最终输出 PDF（含修正书签 + 复制第一页到末尾）")
    ap.add_argument("--dest", default="Fit", choices=["Fit", "FitH", "FitV"], help="书签目的地类型（默认 Fit）")
    ap.add_argument("--set-r2l", action="store_true", help="写入 ViewerPreferences Direction=R2L（右到左翻页）")
    args = ap.parse_args()

    pdf_path = os.path.join(args.workdir, args.pdf)
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(pdf_path)

    input_json = os.path.join(args.workdir, args.tmp_input_json)
    output_json = os.path.join(args.workdir, args.tmp_output_json)
    out_no_bm = os.path.join(args.workdir, args.out_no_bm)
    out_pdf = os.path.join(args.workdir, args.out)

    for tool in ["pdfcpu", "qpdf"]:
        if shutil.which(tool) is None:
            raise RuntimeError(f"缺少命令：{tool}。请先安装并确保在 PATH 中。")

    # 1) 导出目录
    run(["pdfcpu", "bookmarks", "export", pdf_path, input_json])

    # 2) 修正目录（整体前移一位）
    data = load_json(input_json)
    if isinstance(data.get("bookmarks"), list):
        shift_pages_to_previous_original(data["bookmarks"], prev_original=1)
    save_json(data, output_json)

    # 3) 删除原来 pdf 的目录
    run(["pdfcpu", "bookmarks", "remove", pdf_path, out_no_bm])

    # 4) 重建目录（pikepdf）+ 默认复制第一页到末尾
    write_bookmarks_and_dup_first_page_to_end(out_no_bm, output_json, out_pdf, dest_mode=args.dest)

    # 5) 可选：设置 R2L
    if args.set_r2l:
        run(["pdfcpu", "viewerpref", "set", out_pdf, '{"Direction":"R2L"}'])

    print("✅ Done")
    print("Exported:", input_json)
    print("Fixed JSON:", output_json)
    print("No-bookmark PDF:", out_no_bm)
    print("Final PDF:", out_pdf)
    print("Note: 第一页已复制并追加到最后。")


if __name__ == "__main__":
    main()