#!/usr/bin/env python3
import argparse
import pathlib
from string import Template

TEMPLATE_DIR = pathlib.Path(__file__).resolve().parent / "templates"


def load_template_text(default_filename: str, template_path: str | None) -> str:
    if template_path:
        path = pathlib.Path(template_path).resolve()
    else:
        path = TEMPLATE_DIR / default_filename
    return path.read_text(encoding="utf-8")


def shift_heading_depth(lines: list[str], depth: int) -> list[str]:
    shifted: list[str] = []
    for line in lines:
        if line.startswith("#"):
            marker_len = len(line) - len(line.lstrip("#"))
            if marker_len > 0 and (len(line) == marker_len or line[marker_len] == " "):
                shifted.append(("#" * depth) + line)
                continue
        shifted.append(line)
    return shifted


def normalize_report_body(report_path: pathlib.Path) -> str:
    text = report_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if lines and lines[0].startswith("## "):
        lines = lines[1:]
    while lines and not lines[0].strip():
        lines = lines[1:]
    return "\n".join(shift_heading_depth(lines, 1)).strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--report-callgrind")
    parser.add_argument("--report-criterion")
    parser.add_argument("--template-path")
    parser.add_argument("--section-template-path")
    args = parser.parse_args()

    sections: list[str] = []
    section_template = Template(
        load_template_text("report_combined_backend_section.md.tmpl", args.section_template_path)
    )
    if args.report_callgrind:
        path = pathlib.Path(args.report_callgrind)
        if path.exists():
            sections.append(
                section_template.safe_substitute(
                    backend_title="Callgrind",
                    backend_body=normalize_report_body(path),
                ).strip()
            )
    if args.report_criterion:
        path = pathlib.Path(args.report_criterion)
        if path.exists():
            sections.append(
                section_template.safe_substitute(
                    backend_title="Criterion",
                    backend_body=normalize_report_body(path),
                ).strip()
            )

    if not sections:
        raise SystemExit("No backend reports were generated.")

    template = Template(load_template_text("report_combined.md.tmpl", args.template_path))
    markdown = template.safe_substitute(sections="\n\n".join(sections)).rstrip() + "\n"
    pathlib.Path(args.output).write_text(markdown, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
