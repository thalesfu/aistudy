import json

def shift_pages_to_previous_original(bookmarks, prev_original=1):
    """
    前序遍历：每个书签的 page 改成“前一个书签的原始 page”
    - 第一个书签的 page 改成 1（由 prev_original 初始值决定）
    - 返回遍历结束后的“最后一个书签的原始 page”，供上层继续串起来
    """
    for bm in bookmarks:
        # 取出当前原始 page（尽量转成 int）
        cur_original = bm.get("page")
        try:
            cur_original = int(cur_original)
        except (TypeError, ValueError):
            # 如果没有/不是数字，就把它当成 prev_original（不让链断掉）
            cur_original = prev_original

        # 把当前 page 改为前一个原始 page
        bm["page"] = prev_original

        # 更新 prev_original 为“当前原始 page”，然后再处理 kids
        prev_original = cur_original

        kids = bm.get("kids")
        if isinstance(kids, list) and kids:
            prev_original = shift_pages_to_previous_original(kids, prev_original)

    return prev_original


def main(input_file, output_file):
    with open(input_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data.get("bookmarks"), list):
        shift_pages_to_previous_original(data["bookmarks"], prev_original=1)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


if __name__ == "__main__":
    main("input.json", "output.json")