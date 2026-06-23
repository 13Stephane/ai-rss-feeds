#!/usr/bin/env python3
"""Extract and pretty-print embedded Next.js data from HTML files."""

import json
import re
import sys

from lxml import html



def iter_flight_record_values(nextjs_string):
    """Yield (key, value) pairs parsed from a Next.js Flight payload string.

    Records are emitted as `<key>:<value>` and typically begin at line starts.
    This parser anchors to line boundaries to avoid false matches in URLs like
    `https://...`, and accepts alphanumeric keys (e.g. `2e`, `1c`, `a`).
    """
    decoder = json.JSONDecoder()
    pos = 0
    length = len(nextjs_string)

    while pos < length:
        line_end = nextjs_string.find("\n", pos)
        if line_end == -1:
            line_end = length

        line = nextjs_string[pos:line_end]
        separator_idx = line.find(":")

        # Move to the next line by default to guarantee forward progress.
        next_pos = line_end + 1

        # Expect records formatted as <alnum_key>:<json_value>.
        if separator_idx <= 0:
            pos = next_pos
            continue

        key = line[:separator_idx]
        if not key.isalnum():
            pos = next_pos
            continue

        value_start = pos + separator_idx + 1

        # Flight records like I[...] / T... are references, not JSON values.
        if value_start < length and nextjs_string[value_start] in {"I", "T", "H"}:
            pos = next_pos
            continue

        try:
            value, _ = decoder.raw_decode(nextjs_string, value_start)
            yield key, value
        except json.JSONDecodeError:
            # Skip malformed/non-JSON records and continue scanning.
            pass

        pos = next_pos


def extract_nextjs_records(html_file):
    """Return all parsed JSON record values from Next.js Flight data as a list."""
    with open(html_file, "r", encoding="utf-8") as file_handle:
        html_content = file_handle.read()

    document = html.fromstring(html_content)
    records = []

    for script_element in document.xpath("//script"):
        script_text = (script_element.text or "").strip()
        script_id = script_element.get("id")
        script_type = (script_element.get("type") or "").lower()

        if script_id == "__NEXT_DATA__":
            try:
                records.append(json.loads(script_text))
            except json.JSONDecodeError:
                pass
            continue

        if script_type.startswith("application/json"):
            try:
                records.append(json.loads(script_text))
            except json.JSONDecodeError:
                pass
            continue

        if "self.__next_f.push(" not in script_text:
            continue

        pattern = r"self\.__next_f\.push\(\s*(\[.*\])\s*\)"
        match = re.search(pattern, script_text, re.DOTALL)
        if not match:
            continue

        try:
            outer = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue

        if not isinstance(outer, list) or len(outer) < 2:
            continue

        nextjs_string = outer[1]
        for _key, value in iter_flight_record_values(nextjs_string):
            records.append(value)

    return records


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python extract_nextjs.py <html_file>")
        sys.exit(1)

    html_file = sys.argv[1]
    records = extract_nextjs_records(html_file)
    print(json.dumps(records))
