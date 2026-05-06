import argparse
import json
import os
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

try:
    from deep_translator import GoogleTranslator
    import deep_translator.google as google_translator_module
except ImportError:  # pragma: no cover - exercised only when dependency is missing
    GoogleTranslator = None
    google_translator_module = None

XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"
REQUEST_TIMEOUT_SECONDS = 20


def normalize_language_codes(value):
    if not value:
        return []
    if isinstance(value, str):
        raw_codes = value.split(",")
    else:
        raw_codes = value
    return [
        code.strip().replace("_", "-")
        for code in raw_codes
        if code and code.strip()
    ]


def read_language_config(path):
    if not path:
        return []

    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Language config not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    languages = payload.get("languages", [])
    return [
        item["code"]
        for item in languages
        if item.get("code")
        and item.get("code") != "en"
        and item.get("enabled", True)
        and item.get("ui", True)
    ]


def translator_language_code(language_code):
    return language_code.split("-")[0].lower()

def translate_text(text, target_lang):
    if GoogleTranslator is None:
        raise RuntimeError(
            "Missing dependency: deep-translator. Install with `pip install deep-translator`."
        )
    translator = GoogleTranslator(source='auto', target=target_lang)
    if google_translator_module is None:
        return translator.translate(text)

    original_get = google_translator_module.requests.get

    def get_with_timeout(*args, **kwargs):
        kwargs.setdefault("timeout", REQUEST_TIMEOUT_SECONDS)
        return original_get(*args, **kwargs)

    google_translator_module.requests.get = get_with_timeout
    try:
        return translator.translate(text)
    finally:
        google_translator_module.requests.get = original_get

def clone_resource_shell(source_root):
    resx_root = ET.Element("root")
    for child in source_root:
        if child.tag != "data":
            resx_root.append(child)
    return resx_root


def copy_entry(source_entry, translated_value):
    new_entry = ET.Element("data", source_entry.attrib)
    if XML_SPACE not in new_entry.attrib:
        new_entry.set(XML_SPACE, "preserve")
    value_elem = ET.SubElement(new_entry, "value")
    value_elem.text = translated_value

    comment_elem = source_entry.find("comment")
    if comment_elem is not None:
        new_comment = ET.SubElement(new_entry, "comment")
        new_comment.text = comment_elem.text

    return new_entry


def set_entry_value(entry, value):
    value_elem = entry.find("value")
    if value_elem is None:
        value_elem = ET.SubElement(entry, "value")
    value_elem.text = value


def discover_existing_languages(directory, base_name):
    prefix = f"{base_name}."
    suffix = ".resx"
    languages = []
    for file_name in os.listdir(directory):
        if file_name.startswith(prefix) and file_name.endswith(suffix):
            languages.append(file_name[len(prefix):-len(suffix)])
    return sorted(set(languages))


def translate_with_retries(text, target_lang, max_retries, fallback_to_source):
    for attempt in range(max_retries + 1):
        try:
            return translate_text(text, target_lang)
        except Exception as exc:
            if fallback_to_source and isinstance(exc, RuntimeError) and "Missing dependency" in str(exc):
                print(
                    f"Translate fallback ({target_lang}): {type(exc).__name__}: {exc}; using source text"
                )
                return text
            if attempt < max_retries:
                delay = min(2 + attempt, 8)
                print(
                    f"Translate retry ({target_lang}): {type(exc).__name__}: {exc}; retrying in {delay}s"
                )
                time.sleep(delay)
                continue
            if fallback_to_source:
                print(
                    f"Translate fallback ({target_lang}): {type(exc).__name__}: {exc}; using source text"
                )
                return text
            raise


def process_resx_files(directory, force_translate, exclude_languages, base_name="AppRes",
                       target_languages=None, max_retries=2, fallback_to_source=False):
    original_file = os.path.join(directory, f"{base_name}.resx")
    if not os.path.exists(original_file):
        print(f"Original resx file not found: {original_file}")
        return

    tree = ET.parse(original_file)
    root = tree.getroot()
    original_entries = {entry.attrib['name']: entry for entry in root.findall('data')}
    excluded = set(normalize_language_codes(exclude_languages))
    languages = normalize_language_codes(target_languages)
    if not languages:
        languages = discover_existing_languages(directory, base_name)

    for lang_code in languages:
        if lang_code in excluded:
            continue

        file_path = os.path.join(directory, f"{base_name}.{lang_code}.resx")
        file_exists = os.path.exists(file_path)
        if file_exists:
            resx_tree = ET.parse(file_path)
            resx_root = resx_tree.getroot()
        else:
            resx_root = clone_resource_shell(root)

        existing_entries = {entry.attrib['name']: entry for entry in resx_root.findall('data')}
        translated_count = 0
        updated_count = 0
        translator_code = translator_language_code(lang_code)

        for name, orig_entry in original_entries.items():
            orig_value_elem = orig_entry.find('value')
            orig_value = orig_value_elem.text if orig_value_elem is not None else ""
            target_entry = existing_entries.get(name)
            target_value_elem = target_entry.find("value") if target_entry is not None else None
            target_value = target_value_elem.text if target_value_elem is not None else None

            if not force_translate and target_entry is not None and target_value:
                continue

            translated_value = translate_with_retries(
                orig_value,
                translator_code,
                max_retries,
                fallback_to_source) if orig_value else ""
            if translated_value is None:
                translated_value = orig_value
            print(f"Translate ({lang_code}): {orig_value} --> {translated_value}")

            if target_entry is None:
                resx_root.append(copy_entry(orig_entry, translated_value))
                translated_count += 1
            else:
                set_entry_value(target_entry, translated_value)
                updated_count += 1

        if translated_count > 0 or updated_count > 0 or not file_exists:
            ET.indent(resx_root, space="  ")
            resx_tree = ET.ElementTree(resx_root)
            resx_tree.write(file_path, encoding="utf-8", xml_declaration=True)
        print(f"Translate ({lang_code}): Done! new={translated_count}, updated={updated_count}")

    print("\nTranslation process completed!")

def main():
    parser = argparse.ArgumentParser(description="Translate .resx files")
    parser.add_argument("--resx-directory", type=str, help="Path to the .resx directory", required=False)
    parser.add_argument("--base-name", type=str, help="Neutral .resx base name", default="AppRes")
    parser.add_argument("--target-languages", type=str, help="Comma-separated language codes to generate", required=False, default="")
    parser.add_argument("--language-config", type=str, help="JSON config with languages[] entries", required=False)
    parser.add_argument("--exclude-languages", type=str, help="Comma-separated list of languages to exclude", required=False, default="")
    parser.add_argument("--request-timeout", type=int, help="HTTP request timeout in seconds", default=20)
    parser.add_argument("--max-retries", type=int, help="Retries per translated value", default=2)
    parser.add_argument("--fallback-to-source", action="store_true", help="Use source text if translation fails after retries")
    parser.add_argument("--force", action="store_true", help="Force re-translate all entries")
    parser.add_argument("--new-only", action="store_true", help="Only translate new entries")
    
    args = parser.parse_args()
    global REQUEST_TIMEOUT_SECONDS
    REQUEST_TIMEOUT_SECONDS = max(1, args.request_timeout)

    if args.resx_directory:
        exclude_languages = normalize_language_codes(args.exclude_languages)
        target_languages = normalize_language_codes(args.target_languages)
        if not target_languages and args.language_config:
            target_languages = read_language_config(args.language_config)
        if args.force:
            process_resx_files(args.resx_directory, True, exclude_languages,
                               args.base_name, target_languages,
                               args.max_retries, args.fallback_to_source)
            sys.exit(0)
        elif args.new_only:
            process_resx_files(args.resx_directory, False, exclude_languages,
                               args.base_name, target_languages,
                               args.max_retries, args.fallback_to_source)
            sys.exit(0)
    
    while True:
        print("Menu:")
        print("1. Start translation (only new entries)")
        print("2. Force re-translate all entries")
        print("3. Exit")
        choice = input("Choose an option: ")
        
        if choice in ["1", "2"]:
            directory = input("Enter the directory of resx files: ")
            base_name = input("Enter neutral resx base name (default AppRes): ") or "AppRes"
            target_languages = normalize_language_codes(
                input("Enter target languages (comma separated, optional): "))
            exclude_languages = input("Enter languages to exclude (comma separated, optional): ").split(',') if input("Exclude any languages? (y/n): ").lower() == "y" else []
        
        if choice == "1":
            process_resx_files(directory, False, exclude_languages, base_name, target_languages)
        elif choice == "2":
            process_resx_files(directory, True, exclude_languages, base_name, target_languages)
        elif choice == "3":
            print("Exiting...")
            sys.exit(0)
        else:
            print("Invalid option, please choose again.")

if __name__ == "__main__":
    main()
