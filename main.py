import os
import re
import sys
import argparse
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from deep_translator import GoogleTranslator

# Matches {placeholder} interpolation tokens used by the TS i18n `t()` helper.
PLACEHOLDER_RE = re.compile(r"\{[^{}]*\}")

# i18n locale keys -> codes understood by GoogleTranslator.
LANG_ALIASES = {
    "zh": "zh-CN",
    "zh-cn": "zh-CN",
    "zh-tw": "zh-TW",
    "zh-hans": "zh-CN",
    "zh-hant": "zh-TW",
    "he": "iw",
    "pt-br": "pt",
    "nb": "no",
}


def normalize_lang(lang):
    key = lang.strip().lower()
    if key in LANG_ALIASES:
        return LANG_ALIASES[key]
    if key in ("zh-cn", "zh-tw"):
        return LANG_ALIASES[key]
    return key.split("-")[0]


class ProgressPrinter:
    """Live progress: a percentage bar plus the last few translated lines."""

    def __init__(self, total, recent=4):
        self.total = total
        self.recent = recent
        self.count = 0
        self.lines = []
        self._printed = 0
        if total == 0:
            print("Nothing to translate (no missing keys).")

    def _render(self):
        pct = (self.count / self.total * 100) if self.total else 100.0
        filled = int(pct / 100 * 30)
        bar = "#" * filled + "-" * (30 - filled)
        block = [f"[{bar}] {pct:5.1f}%  ({self.count}/{self.total})"]
        block += [f"  {line}" for line in self.lines[-self.recent:]]

        out = sys.stdout
        if self._printed:
            out.write(f"\x1b[{self._printed}A")
        for line in block:
            out.write("\x1b[2K" + line[:200] + "\n")
        out.flush()
        self._printed = len(block)

    def step(self, message):
        self.count += 1
        self.lines.append(message)
        self._render()

    def done(self):
        if self.total:
            self._render()


def translate_text(text, target_lang):
    if text is None or str(text).strip() == "":
        return text
    translator = GoogleTranslator(source='auto', target=normalize_lang(target_lang))
    return translator.translate(text)


def translate_preserving_placeholders(text, target_lang):
    """Translate `text` while keeping {placeholder} tokens untouched."""
    if text is None or text.strip() == "":
        return text

    tokens = PLACEHOLDER_RE.findall(text)
    if not tokens:
        return translate_text(text, target_lang)

    # Swap placeholders for sentinels that survive machine translation intact.
    protected = text
    restore = []
    for i, token in enumerate(tokens):
        sentinel = f"XPLH{i}X"
        protected = protected.replace(token, sentinel, 1)
        # Tolerate case changes and stray spaces the translator may introduce.
        pattern = re.compile(r"\s*".join(re.escape(c) for c in sentinel), re.IGNORECASE)
        restore.append((pattern, token))

    translated = translate_text(protected, target_lang) or protected
    for pattern, token in restore:
        translated = pattern.sub(token, translated)
    return translated


def run_translations(worklist, translate_fn, workers, progress=None, describe=None):
    """Translate `worklist` items concurrently, returning (item, translated) pairs.

    Only the network-bound `translate_fn` calls run in the thread pool; results are
    consumed on the calling thread, so progress printing and file writing stay serial.
    """
    results = []
    if not worklist:
        return results

    workers = max(1, min(workers, len(worklist)))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        for item, translated in executor.map(translate_fn, worklist):
            results.append((item, translated))
            if progress is not None:
                progress.step(describe(item, translated) if describe else str(translated))
            elif describe is not None:
                print(describe(item, translated))
    return results


# ----------------------------------------------------------------------------
# TypeScript i18n support (inline `const DICTS: Record<Lang, Dict> = { ... }`)
# ----------------------------------------------------------------------------

def _find_matching_brace(text, open_index):
    """Return the index of the `}` matching the `{` at `open_index`."""
    depth = 0
    in_str = None
    i = open_index
    while i < len(text):
        ch = text[i]
        if in_str:
            if ch == "\\":
                i += 2
                continue
            if ch == in_str:
                in_str = None
        elif ch in "\"'`":
            in_str = ch
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    raise ValueError("Unbalanced braces while parsing DICTS object")


def _parse_string_entries(body):
    """Parse a flat JS object body into an ordered list of (key, value) pairs.

    Only string-valued entries are returned; keys may be quoted or bare.
    """
    entries = []
    i = 0
    n = len(body)

    def read_string(idx):
        quote = body[idx]
        idx += 1
        buf = []
        while idx < n:
            ch = body[idx]
            if ch == "\\":
                buf.append(body[idx:idx + 2])
                idx += 2
                continue
            if ch == quote:
                return "".join(buf), idx + 1
            buf.append(ch)
            idx += 1
        raise ValueError("Unterminated string in DICTS entry")

    while i < n:
        ch = body[i]
        if ch in " \t\r\n,":
            i += 1
            continue
        if body.startswith("//", i):
            i = body.find("\n", i)
            if i == -1:
                break
            continue
        if body.startswith("/*", i):
            end = body.find("*/", i)
            i = end + 2 if end != -1 else n
            continue

        # --- key ---
        if ch in "\"'`":
            key, i = read_string(i)
        else:
            m = re.match(r"[A-Za-z0-9_$.\-]+", body[i:])
            if not m:
                i += 1
                continue
            key = m.group(0)
            i += m.end()

        while i < n and body[i] in " \t\r\n":
            i += 1
        if i >= n or body[i] != ":":
            continue
        i += 1
        while i < n and body[i] in " \t\r\n":
            i += 1
        if i >= n:
            break

        # --- value ---
        if body[i] in "\"'`":
            raw, i = read_string(i)
            value = raw.encode().decode("unicode_escape") if "\\" in raw else raw
            entries.append((key, value))
        else:
            # Non-string value (nested object, number, etc.) - skip it.
            m = re.match(r"[^,{}\[\]]+", body[i:])
            i += m.end() if m else 1
    return entries


def _escape_ts_string(value):
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def process_i18n_ts(file_path, force_translate, exclude_languages, source_lang, workers=8):
    with open(file_path, "r", encoding="utf-8") as fh:
        content = fh.read()

    match = re.search(r"(?:const|let|var)\s+DICTS\b[^=]*=\s*", content)
    if not match:
        print("DICTS declaration not found in i18n file!")
        return

    brace_start = content.index("{", match.end())
    brace_end = _find_matching_brace(content, brace_start)
    dicts_body = content[brace_start + 1:brace_end]

    # Split the DICTS body into `lang: { ... }` sections, preserving order.
    langs = []
    i = 0
    while i < len(dicts_body):
        m = re.match(r"\s*([A-Za-z0-9_$'\"-]+)\s*:\s*\{", dicts_body[i:])
        if not m:
            i += 1
            continue
        lang_name = m.group(1).strip("'\"")
        inner_open = i + m.end() - 1
        inner_close = _find_matching_brace(dicts_body, inner_open)
        inner_body = dicts_body[inner_open + 1:inner_close]
        langs.append([lang_name, _parse_string_entries(inner_body)])
        i = inner_close + 1

    lang_map = {name: dict(entries) for name, entries in langs}
    if source_lang not in lang_map:
        print(f"Source language '{source_lang}' not found in DICTS (have: {', '.join(lang_map)})")
        return

    source_entries = next(entries for name, entries in langs if name == source_lang)

    # Build the full worklist first so progress can be shown as a percentage.
    worklist = []
    for name, _ in langs:
        if name == source_lang or name in exclude_languages:
            continue
        existing = lang_map[name]
        for key, src_value in source_entries:
            if not force_translate and key in existing and existing[key].strip() != "":
                continue
            worklist.append((name, key, src_value))

    progress = ProgressPrinter(len(worklist), recent=4)
    results = run_translations(
        worklist,
        lambda item: (item, translate_preserving_placeholders(item[2], item[0])),
        workers,
        progress=progress,
        describe=lambda item, translated: f"({item[0]}) {item[1]}: {item[2]} --> {translated}",
    )
    for (name, key, _src), translated in results:
        lang_map[name][key] = translated
    progress.done()

    # Rebuild the DICTS object using the source key order for every language.
    indent = "  "
    blocks = []
    for name, _ in langs:
        values = lang_map[name]
        ordered_keys = [k for k, _ in source_entries]
        ordered_keys += [k for k in values if k not in ordered_keys]
        lines = [f"{indent}{name}: {{"]
        for key in ordered_keys:
            if key not in values:
                continue
            key_repr = f'"{key}"'
            lines.append(f'{indent}{indent}{key_repr}: "{_escape_ts_string(values[key])}",')
        lines.append(f"{indent}}},")
        blocks.append("\n".join(lines))

    new_body = "\n" + "\n".join(blocks) + "\n"
    new_content = content[:brace_start + 1] + new_body + content[brace_end:]
    with open(file_path, "w", encoding="utf-8") as fh:
        fh.write(new_content)
    print("\ni18n TypeScript translation completed!")

def process_resx_files(directory, force_translate, exclude_languages, workers=8):
    original_file = os.path.join(directory, "AppRes.resx")
    if not os.path.exists(original_file):
        print("Original resx file not found!")
        return

    tree = ET.parse(original_file)
    root = tree.getroot()
    original_entries = {entry.attrib['name']: entry for entry in root.findall('data')}

    # --- Phase A: collect per-file targets and the global translation worklist ---
    targets = []   # (lang_code, file_path, resx_root)
    worklist = []  # (lang_code, name, orig_entry, orig_value)
    for file_name in sorted(os.listdir(directory)):
        if not (file_name.startswith("AppRes.") and file_name.endswith(".resx") and file_name != "AppRes.resx"):
            continue
        lang_code = file_name[7:-5]  # Extracting language code from filename
        if lang_code in exclude_languages:
            continue

        file_path = os.path.join(directory, file_name)
        if os.path.exists(file_path):
            resx_root = ET.parse(file_path).getroot()
        else:
            resx_root = ET.Element("root")
            for element in root.findall("resheader"):
                resx_root.append(element)
            for schema in root.findall("{http://www.w3.org/2001/XMLSchema}schema"):
                resx_root.append(schema)

        existing_entries = {entry.attrib['name']: entry for entry in resx_root.findall('data')}
        targets.append((lang_code, file_path, resx_root))

        for name, orig_entry in original_entries.items():
            if force_translate or name not in existing_entries:
                orig_value_elem = orig_entry.find('value')
                orig_value = orig_value_elem.text if orig_value_elem is not None else ""
                worklist.append((lang_code, name, orig_entry, orig_value))

    # --- Phase B: translate every missing key across all languages in parallel ---
    progress = ProgressPrinter(len(worklist), recent=4)
    results = run_translations(
        worklist,
        lambda item: (item, translate_text(item[3], item[0][:2])),
        workers,
        progress=progress,
        describe=lambda item, translated: f"({item[0]}) {item[1]}: {item[3]} --> {translated}",
    )
    progress.done()

    # --- Phase C: build and write each file exactly once, on this thread ---
    by_lang = {}
    for (lang_code, name, orig_entry, _orig_value), translated in results:
        new_entry = ET.Element("data", name=name)
        if 'xml:space' in orig_entry.attrib:
            new_entry.set("xml:space", orig_entry.attrib['xml:space'])
        value_elem = ET.SubElement(new_entry, "value")
        value_elem.text = translated

        comment_elem = orig_entry.find("comment")
        if comment_elem is not None:
            new_comment = ET.SubElement(new_entry, "comment")
            new_comment.text = comment_elem.text

        by_lang.setdefault(lang_code, []).append(new_entry)

    for lang_code, file_path, resx_root in targets:
        for new_entry in by_lang.get(lang_code, []):
            resx_root.append(new_entry)
        ET.ElementTree(resx_root).write(file_path, encoding="utf-8", xml_declaration=True)
        print(f"Translate ({lang_code}): Done!")

    print("\nTranslation process completed!")

def main():
    parser = argparse.ArgumentParser(description="Translate .resx files")
    parser.add_argument("--resx-directory", type=str, help="Path to the .resx directory", required=False)
    parser.add_argument("--i18n-file", type=str, help="Path to a TypeScript i18n file (inline `const DICTS` object)", required=False)
    parser.add_argument("--i18n-source-lang", type=str, help="Source language key inside DICTS (default: en)", default="en")
    parser.add_argument("--exclude-languages", type=str, help="Comma-separated list of languages to exclude", required=False, default="")
    parser.add_argument("--force", action="store_true", help="Force re-translate all entries")
    parser.add_argument("--new-only", action="store_true", help="Only translate new entries")
    parser.add_argument("--workers", type=int, default=8, help="Parallel translation workers (default: 8)")

    args = parser.parse_args()

    exclude_languages = args.exclude_languages.split(',') if args.exclude_languages else []

    if args.i18n_file:
        if args.force:
            process_i18n_ts(args.i18n_file, True, exclude_languages, args.i18n_source_lang, args.workers)
            sys.exit(0)
        elif args.new_only:
            process_i18n_ts(args.i18n_file, False, exclude_languages, args.i18n_source_lang, args.workers)
            sys.exit(0)

    if args.resx_directory:
        if args.force:
            process_resx_files(args.resx_directory, True, exclude_languages, args.workers)
            sys.exit(0)
        elif args.new_only:
            process_resx_files(args.resx_directory, False, exclude_languages, args.workers)
            sys.exit(0)
    
    while True:
        print("Menu:")
        print("1. resx: Start translation (only new entries)")
        print("2. resx: Force re-translate all entries")
        print("3. i18n.ts: Translate missing keys (only new)")
        print("4. i18n.ts: Force re-translate all keys")
        print("5. Exit")
        choice = input("Choose an option: ")

        if choice in ["1", "2", "3", "4"]:
            exclude_languages = input("Enter languages to exclude (comma separated, optional): ").split(',') if input("Exclude any languages? (y/n): ").lower() == "y" else []
            try:
                workers = int(input("Parallel workers [8]: ").strip() or "8")
            except ValueError:
                workers = 8

        if choice in ["1", "2"]:
            directory = input("Enter the directory of resx files: ")
            process_resx_files(directory, choice == "2", exclude_languages, workers)
        elif choice in ["3", "4"]:
            i18n_file = input("Enter the path to the i18n .ts file: ")
            source_lang = input("Source language key [en]: ").strip() or "en"
            process_i18n_ts(i18n_file, choice == "4", exclude_languages, source_lang, workers)
        elif choice == "5":
            print("Exiting...")
            sys.exit(0)
        else:
            print("Invalid option, please choose again.")

if __name__ == "__main__":
    main()
