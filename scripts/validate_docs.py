#!/usr/bin/env python3
"""Validate Markdown documents against the requirement/development-plan templates.

用法:
    python3 validate_docs.py [file ...]
    python3 validate_docs.py --requirement <需求澄清.md>
    python3 validate_docs.py --dev-plan <开发方案.md>
不给文件时，检查当前目录下 *需求澄清*.md 和 *开发方案*.md。
"""

import glob
import re
import sys
from typing import List

# (名称, 列数, 数据行数)，按需求澄清模板中表格出现顺序
EXPECTED_REQ_TABLES = [
    ("需求来源", 2, 7),
    ("需求梳理", 4, 10),
    ("场景一", 4, 8),
    ("场景二", 4, 8),
    ("Checklist", 5, 7),
    ("A类指标", 4, 2),
    ("B类指标", 4, 4),
    ("影响范围映射", 4, 3),
    ("内部评审", 3, 6),
]

REQ_HEADINGS = [
    "需求来源",
    "需求梳理",
    "验收场景",
    "Checklist",
    "影响范围",
    "A图",
    "内部评审",
]

REQ_SCENARIO_HEADINGS = ["场景一", "场景二", "场景三"]

DEV_HEADINGS = [
    "1 修订记录",
    "2 功能规格",
    "2.1 功能需求",
    "2.2 功能说明",
    "2.3 外部接口",
    "3 功能设计",
    "3.1 对其他工具或特性的影响",
    "3.2 实现",
    "3.3 性能",
    "3.4 测试验收",
    "3.5 风险",
    "3.6 未来扩展的可能性",
    "3.7 可重用的软件组件",
    "4 附录",
]


def split_row(line: str) -> int:
    """返回表格行的列数；支持 \\| 转义。"""
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return len(re.split(r"(?<!\\)\|", s))


def collect_tables(lines: List[str]):
    """返回 [(起始行号, 列数, 数据行数, 表头)]。"""
    tables = []
    i = 0
    while i < len(lines):
        header = lines[i].strip()
        sep = lines[i + 1].strip() if i + 1 < len(lines) else ""
        if header.startswith("|") and re.match(r"^\|[\s:|-]+\|$", sep):
            cols = split_row(header)
            j = i + 2
            while j < len(lines) and lines[j].strip().startswith("|"):
                j += 1
            tables.append((i + 1, cols, j - i - 2, header))
            i = j
        else:
            i += 1
    return tables


def check_table_columns(lines: List[str]) -> List[str]:
    issues = []  # type: List[str]
    for start, cols, rows, _header in collect_tables(lines):
        for offset in range(rows):
            line_no = start + 2 + offset
            row_cols = split_row(lines[line_no - 1])
            if row_cols != cols:
                issues.append(
                    f"  line {line_no}: {row_cols} 列，表头 {cols} 列: {lines[line_no - 1].strip()[:100]}"
                )
    return issues


def version_lines(lines: List[str]) -> List[str]:
    out = []  # type: List[str]
    for idx, line in enumerate(lines[:40], 1):
        if re.search(r"\bv\d+\.\d+\b", line):
            out.append(f"  line {idx}: {line.strip()[:160]}")
    return out


def heading_text(line: str):
    """返回标题行的文本；不是标题行返回 None。"""
    match = re.match(r"^#{1,4}\s+(.+)$", line.strip())
    return match.group(1).strip() if match else None


def heading_order(lines: List[str], headings: List[str], label: str) -> bool:
    """检查标题是否齐全且按给定顺序出现。"""
    ok = True
    positions = []
    print(f"{label}章节检查:")
    for heading in headings:
        pos = next(
            (i for i, line in enumerate(lines) if (heading_text(line) or "").startswith(heading)),
            -1,
        )
        positions.append(pos)
        print(f"  {'OK' if pos >= 0 else 'FAIL'} {heading}: line {pos + 1 if pos >= 0 else '缺失'}")
        if pos < 0:
            ok = False
    if all(p >= 0 for p in positions) and positions == sorted(positions):
        print("  OK 章节顺序正确")
    else:
        print("  FAIL 章节顺序不正确")
        ok = False
    return ok


def check_req_template(lines: List[str], tables) -> bool:
    ok = True

    print("需求澄清模板形状检查:")
    if len(tables) != len(EXPECTED_REQ_TABLES):
        print(f"  FAIL 表格数量 {len(tables)}，期望 {len(EXPECTED_REQ_TABLES)}")
        ok = False
    for idx, (name, exp_cols, exp_rows) in enumerate(EXPECTED_REQ_TABLES):
        if idx >= len(tables):
            print(f"  FAIL {name}: 缺少表格")
            ok = False
            continue
        start, cols, rows, _header = tables[idx]
        status = "OK" if (cols, rows) == (exp_cols, exp_rows) else "FAIL"
        print(f"  {status} {name}: {cols}列×{rows}行（期望 {exp_cols}列×{exp_rows}行），line {start}")
        if status == "FAIL":
            ok = False

    if not heading_order(lines, REQ_HEADINGS, "需求澄清一级"):
        ok = False
    if not heading_order(lines, REQ_SCENARIO_HEADINGS, "需求澄清场景"):
        ok = False
    return ok


def check_dev_template(lines: List[str]) -> bool:
    return heading_order(lines, DEV_HEADINGS, "开发方案")


def resolve_files(args: List[str], check_req: bool, check_dev: bool) -> List[str]:
    files = [a for a in args if not a.startswith("--")]
    if files:
        return files
    found = []  # type: List[str]
    if check_req:
        found.extend(sorted(glob.glob("*需求澄清*.md")))
    if check_dev:
        found.extend(sorted(glob.glob("*开发方案*.md")))
    if not found:
        found.extend(sorted(glob.glob("*需求澄清*.md")))
        found.extend(sorted(glob.glob("*开发方案*.md")))
    out = []  # type: List[str]
    for path in found:
        if path not in out:
            out.append(path)
    return out


def main(argv: List[str]) -> int:
    args = argv[1:]
    check_req = "--requirement" in args
    check_dev = "--dev-plan" in args
    files = resolve_files(args, check_req, check_dev)
    if not files:
        print("未找到文件；请显式传入 Markdown 路径。")
        return 2

    bad = False
    for path in files:
        try:
            with open(path, encoding="utf-8") as fh:
                lines = fh.read().splitlines()
        except OSError as exc:
            print(f"\n=== {path} ===\n读取失败: {exc}")
            bad = True
            continue

        print(f"\n=== {path} ===")
        print(f"行数: {len(lines)}")

        tables = collect_tables(lines)
        print(f"表格数量: {len(tables)}")
        for start, cols, rows, header in tables:
            print(f"  line {start}: {cols}列×{rows}行  {header[:70]}")

        table_issues = check_table_columns(lines)
        print(f"表格列数问题: {len(table_issues)}")
        for issue in table_issues:
            print(issue)
        if table_issues:
            bad = True

        print("版本号出现位置:")
        for line in version_lines(lines):
            print(line)

        print("标题树:")
        for idx, line in enumerate(lines, 1):
            if re.match(r"^#{1,4} ", line):
                print(f"  line {idx}: {line}")

        if check_req and not check_req_template(lines, tables):
            bad = True
        if check_dev and not check_dev_template(lines):
            bad = True

    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
