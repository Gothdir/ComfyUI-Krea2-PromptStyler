"""
Converts the style spreadsheet (TSV export) into styles.json for the
hierarchical Krea2 Prompt Styler node.

Usage:
    python tools/build_styles.py <input.tsv> [output.json] [report.md]

Expected columns (header row, tab separated):
    Order, Category, Medium, Family / Subcategory, Era / Period,
    Style Name, Wildcard Style, Original Row

Output structure:
    { Category: { Medium: { Family: { Style Name: {"era": ..., "text": ...} } } } }

Rules:
  * "text" is the Wildcard Style without its leading "Style Name:" (the node adds it).
  * Punctuation cleanup only (spacing, double/trailing commas, sentence-start capitals,
    missing final period, stray [website] citation tags). Words are not changed.
  * Names repeated in the sheet: identical text -> one copy kept; different text ->
    "Name (v1)", "Name (v2)" in sheet order.
  * Order of categories/mediums/families follows first appearance in the sheet;
    styles inside a family are sorted by name.
"""
import collections
import csv
import json
import os
import re
import sys

CIT = r"\s*\[[a-z0-9][a-z0-9.\-]*\.[a-z]{2,}\]"
ABBREV = {"inc", "jr", "sr", "co", "ltd", "dr", "st", "vs", "etc", "mr", "mrs", "ms", "no", "approx"}
CONNECTORS = {"and", "or", "the", "a", "an", "of", "with", "to", "in", "by", "for", "on", "as", "into", "its", "that", "which", "but"}

def fix(d):
    s = d
    applied = []

    def sub(label, pattern, repl, flags=0):
        nonlocal s
        new, n = re.subn(pattern, repl, s, flags=flags)
        if n:
            applied.append(label)
            s = new

    sub("stray [website] citation tag removed", CIT, "", re.I)
    sub("double comma collapsed", r",(\s*,)+", ",")
    sub("comma before 'Influenced by' -> period", r",\s*(?=Influenced by:)", ". ")
    sub("missing space before 'Influenced by'", r"\.(?=Influenced by:)", ". ")
    sub("missing space after 'Influenced by:'", r"(Influenced by):(?=\S)", r"\1: ")
    sub("',.' -> '.'", r",\.", ".")
    sub("space before comma/period", r"\s+(?=[,.;])", "")
    sub("missing space after comma", r",(?=[A-Za-z(])", ", ")
    sub("double spaces", r"[ ]{2,}", " ")
    s2 = s.strip()
    if s2 != s:
        applied.append("edge whitespace")
        s = s2
    if re.search(r"[,;]+$", s):
        applied.append("trailing comma/'.,' -> period")
        s = re.sub(r"[,;]+$", "", s)
        s = re.sub(r"\.$", "", s)
        s = s + "."

    def cap(m):
        before = s[:m.start()]
        w = re.search(r"([A-Za-z]+)$", before)
        if w and w.group(1).lower() in ABBREV:
            return m.group(0)
        return m.group(1) + m.group(2).upper()

    new = re.sub(r"(?<=[a-z0-9\)])(\.\s+)([a-z])", cap, s)
    if new != s:
        applied.append("lowercase sentence start")
        s = new
    if not re.search(r"[.!?)\"”]$", s):
        last = re.search(r"([A-Za-z]+)$", s)
        lw = last.group(1).lower() if last else ""
        if lw in CONNECTORS or lw.endswith("ly"):
            applied.append("LEFT ALONE: ends mid-phrase")
        else:
            s += "."
            applied.append("missing final period")
    return s, applied


def main():
    src = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "styles.json")
    report = sys.argv[3] if len(sys.argv) > 3 else None

    rows = []
    with open(src, encoding="utf-8", newline="") as fh:
        rd = csv.reader(fh, delimiter="\t", quoting=csv.QUOTE_NONE)
        header = next(rd)
        for i, r in enumerate(rd, start=2):
            if not r or not any(x.strip() for x in r):
                continue
            if len(r) != len(header):
                raise SystemExit(f"line {i}: expected {len(header)} fields, got {len(r)}")
            rec = dict(zip(header, r))
            name = rec["Style Name"].strip()
            wild = rec["Wildcard Style"]
            if not wild.startswith(rec["Style Name"] + ":"):
                raise SystemExit(f"line {i}: Wildcard Style does not start with '{name}:'")
            if ":" in name:
                raise SystemExit(f"line {i}: colon in style name '{name}'")
            raw = wild[len(rec["Style Name"]) + 1:].strip()
            text, applied = fix(raw)
            rows.append(dict(line=i, name=name, cat=rec["Category"].strip(), med=rec["Medium"].strip(),
                             fam=rec["Family / Subcategory"].strip(), era=rec["Era / Period"].strip(),
                             raw=raw, text=text, applied=applied))

    by_name = collections.OrderedDict()
    for r in rows:
        by_name.setdefault(r["name"], []).append(r)

    kept = []
    dropped_identical = []
    versioned = []
    for name, rs in by_name.items():
        uniq = []
        for r in rs:
            if any(r["text"] == u["text"] for u in uniq):
                dropped_identical.append(r)
            else:
                uniq.append(r)
        if len(uniq) == 1:
            uniq[0]["final"] = name
        else:
            for k, r in enumerate(uniq, start=1):
                r["final"] = f"{name} (v{k})"
            versioned.append((name, uniq))
        kept.extend(uniq)

    # Names must stay unique after the node replaces "/" with U+2215
    finals = [r["final"].replace("/", "\u2215") for r in kept]
    dup = [n for n, c in collections.Counter(finals).items() if c > 1]
    if dup:
        raise SystemExit(f"name collision: {dup}")

    tree = collections.OrderedDict()
    for r in kept:
        tree.setdefault(r["cat"], collections.OrderedDict()).setdefault(r["med"], collections.OrderedDict()) \
            .setdefault(r["fam"], {})[r["final"]] = {"era": r["era"], "text": r["text"]}
    for cat in tree.values():
        for med in cat.values():
            for fam, styles in med.items():
                med[fam] = {k: styles[k] for k in sorted(styles, key=str.lower)}

    alnum = lambda t: re.sub(r"[^a-z0-9]", "", t.lower())
    for r in kept:
        assert alnum(re.sub(CIT, "", r["raw"], flags=re.I)) == alnum(r["text"]), r["name"]
        assert r["text"]

    with open(out, "w", encoding="utf-8", newline="") as fh:
        fh.write(json.dumps(tree, indent=2, ensure_ascii=False))

    n_med = sum(len(c) for c in tree.values())
    n_fam = sum(len(m) for c in tree.values() for m in c.values())
    print(f"rows: {len(rows)} | styles written: {len(kept)} | identical repeats dropped: {len(dropped_identical)} "
          f"| renamed to (vN): {sum(len(u) for _, u in versioned)}")
    print(f"categories: {len(tree)} | mediums: {n_med} | families: {n_fam}")
    changed = [r for r in rows if r["raw"] != r["text"]]
    print(f"descriptions cleaned: {len(changed)}")
    left = [r["name"] for r in rows if any(a.startswith("LEFT") for a in r["applied"])]
    if left:
        print("ends mid-phrase (left alone):", left)
    stale = [r["name"] for r in kept if re.match(r"^[A-Z][^.:]{0,60}:\s", r["text"])]
    if stale:
        print("text starts with another label (check):", stale)

    if report:
        L = ["# styles.json build report\n",
             f"- Sheet rows: {len(rows)}; styles written: {len(kept)}",
             f"- Identical repeats dropped: {len(dropped_identical)} ({', '.join(sorted({r['name'] for r in dropped_identical})) or 'none'})",
             "- Names kept as versions:"]
        for name, uniq in versioned:
            L.append(f"  - {name}: " + "; ".join(f"{r['final']} (sheet line {r['line']}, {r['cat']} > {r['med']} > {r['fam']})" for r in uniq))
        L.append(f"- Descriptions with punctuation fixes: {len(changed)}")
        if left:
            L.append("- Ends mid-phrase: " + ", ".join(left))
        if stale:
            L.append("- Text starts with another label: " + ", ".join(stale))
        open(report, "w", encoding="utf-8").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
