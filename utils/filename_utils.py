import re


def sanitize_filename(name: str) -> str:
    illegal_chars = r'[\\/:*?"<>|]'
    sanitized = re.sub(illegal_chars, "_", name)
    sanitized = sanitized.strip(". ")
    if len(sanitized) > 200:
        sanitized = sanitized[:200]
    return sanitized


def build_filename(title: str, page_name: str, page_index: int, total_pages: int, ext: str) -> str:
    safe_title = sanitize_filename(title)
    safe_page_name = sanitize_filename(page_name)
    if total_pages == 1:
        return f"{safe_title}.{ext}"
    return f"{safe_title} - P{page_index} {safe_page_name}.{ext}"
