"""Run pytest and render a compact HTML report for Finch tests."""

from __future__ import annotations

import argparse
import html
import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CaseResult:
    classname: str
    name: str
    status: str
    time: str
    message: str = ""
    details: str = ""


def run_pytest(repo_root: Path, pytest_args: list[str]) -> int:
    junit_path = repo_root / "reports" / "junit.xml"
    cmd = [sys.executable, "-m", "pytest", "--junitxml", str(junit_path), *pytest_args]
    completed = subprocess.run(cmd, cwd=repo_root, check=False)
    return completed.returncode


def parse_junit_xml(junit_path: Path) -> tuple[int, int, int, float, list[CaseResult]]:
    tree = ET.parse(junit_path)
    root = tree.getroot()

    totals = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0, "time": 0.0}
    results: list[CaseResult] = []

    for testsuite in root.iter("testsuite"):
        totals["tests"] += int(testsuite.attrib.get("tests", "0"))
        totals["failures"] += int(testsuite.attrib.get("failures", "0"))
        totals["errors"] += int(testsuite.attrib.get("errors", "0"))
        totals["skipped"] += int(testsuite.attrib.get("skipped", "0"))
        totals["time"] += float(testsuite.attrib.get("time", "0"))

        for testcase in testsuite.iter("testcase"):
            status = "passed"
            message = ""
            details = ""
            failure = testcase.find("failure")
            error = testcase.find("error")
            skipped = testcase.find("skipped")
            if failure is not None:
                status = "failed"
                message = failure.attrib.get("message", "Failed")
                details = failure.text or ""
            elif error is not None:
                status = "error"
                message = error.attrib.get("message", "Error")
                details = error.text or ""
            elif skipped is not None:
                status = "skipped"
                message = skipped.attrib.get("message", "Skipped")
                details = skipped.text or ""

            results.append(
                CaseResult(
                    classname=testcase.attrib.get("classname", ""),
                    name=testcase.attrib.get("name", ""),
                    status=status,
                    time=testcase.attrib.get("time", "0"),
                    message=message,
                    details=details,
                )
            )

    return totals["tests"], totals["failures"] + totals["errors"], totals["skipped"], totals["time"], results


def render_html(output_path: Path, totals: tuple[int, int, int, float], results: list[TestCaseResult]) -> None:
    tests, failed, skipped, elapsed, _ = totals
    rows = []
    for result in results:
        details = html.escape(result.details).replace("\n", "<br>")
        message = html.escape(result.message)
        rows.append(
            f"""
            <tr class="{result.status}">
              <td>{html.escape(result.classname)}</td>
              <td>{html.escape(result.name)}</td>
              <td>{result.status}</td>
              <td>{html.escape(result.time)}</td>
              <td>{message}</td>
              <td><details><summary>Trace</summary><pre>{details}</pre></details></td>
            </tr>
            """
        )

    html_doc = f"""<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Finch test report</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 24px; color: #17212b; background: #f6f8fb; }}
    .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin-bottom: 24px; }}
    .card {{ background: white; border-radius: 14px; padding: 16px; box-shadow: 0 1px 3px rgba(0,0,0,.08); }}
    table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 14px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,.08); }}
    th, td {{ padding: 12px; border-bottom: 1px solid #e6eaf0; text-align: left; vertical-align: top; }}
    th {{ background: #eef3f8; }}
    tr.failed {{ background: #fff2f2; }}
    tr.error {{ background: #fff7eb; }}
    tr.skipped {{ background: #f4f6f8; color: #667085; }}
    pre {{ white-space: pre-wrap; margin: 0; }}
  </style>
</head>
<body>
  <h1>Finch test report</h1>
  <div class="summary">
    <div class="card"><strong>Total</strong><div>{tests}</div></div>
    <div class="card"><strong>Failed</strong><div>{failed}</div></div>
    <div class="card"><strong>Skipped</strong><div>{skipped}</div></div>
    <div class="card"><strong>Duration</strong><div>{elapsed:.2f}s</div></div>
  </div>
  <table>
    <thead>
      <tr><th>Suite</th><th>Test</th><th>Status</th><th>Time</th><th>Message</th><th>Details</th></tr>
    </thead>
    <tbody>
      {''.join(rows)}
    </tbody>
  </table>
</body>
</html>
"""
    output_path.write_text(html_doc, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pytest_args", nargs=argparse.REMAINDER, help="Arguments passed through to pytest.")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    reports_dir = repo_root / "reports"
    reports_dir.mkdir(exist_ok=True)

    pytest_args = args.pytest_args
    if pytest_args[:1] == ["--"]:
        pytest_args = pytest_args[1:]

    exit_code = run_pytest(repo_root, pytest_args)
    junit_path = reports_dir / "junit.xml"

    if junit_path.exists():
        totals = parse_junit_xml(junit_path)
        render_html(reports_dir / "test-report.html", totals, totals[4])
        tests, failed, skipped, elapsed, _ = totals
        print(f"\nReport: reports/test-report.html")
        print(f"Summary: {tests} tests, {failed} failed, {skipped} skipped, {elapsed:.2f}s")
    else:
        print("JUnit report was not created.", file=sys.stderr)

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
