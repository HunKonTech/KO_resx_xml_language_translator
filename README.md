# Translation Script Documentation

## English

### Description
This Python script automates the translation of `.resx` resource files for a project. It takes the base resource file (`AppRes.resx`), detects other language-specific `.resx` files in the same directory, and translates missing or outdated entries using Google Translate. It provides a menu-driven interface for user interaction or can be run with command-line arguments. Users can specify languages to exclude from translation.

### How it Works
1. The script checks for `AppRes.resx` in the given directory.
2. It iterates over all `.resx` files, excluding specified languages.
3. It loads existing translations if available; otherwise, it creates a new `.resx` file.
4. It translates missing or outdated entries using Google Translate.
5. The translated text is inserted into the respective `.resx` files.
6. The script allows users to run it in interactive mode or via command-line arguments.

### Compilation & Execution

#### Linux
1. Ensure Python 3 is installed:
   ```sh
   sudo apt install python3
   ```
2. Install dependencies:
   ```sh
   pip install deep-translator
   ```
3. Run the script:
   ```sh
   python3 main.py --new-only --resx-directory /path/to/resx --exclude-languages "fr,de"
   ```
4. Create an executable:
   ```sh
   pyinstaller --onefile --console --hidden-import=deep_translator.main main.py
   ```

#### Windows
1. Ensure Python 3 is installed (download from [Python website](https://www.python.org/downloads/)).
2. Install dependencies:
   ```cmd
   pip install deep-translator
   ```
3. Run the script:
   ```cmd
   python main.py --new-only --resx-directory C:\path\to\resx --exclude-languages "fr,de"
   ```
4. Create an executable:
   ```cmd
   pyinstaller --onefile --console --hidden-import=deep_translator.main main.py
   ```

#### macOS
1. Ensure Python 3 is installed. You can use the official installer from [Python website](https://www.python.org/downloads/) or Homebrew:
   ```sh
   brew install python
   ```
2. Install dependencies:
   ```sh
   pip3 install deep-translator
   ```
3. Run the script:
   ```sh
   python3 main.py --new-only --resx-directory /path/to/resx --exclude-languages "fr,de"
   ```
4. Create an executable:
   ```sh
   pyinstaller --onefile --console --hidden-import=deep_translator.main main.py
   ```

### Dependencies
- `deep-translator` (install using `pip install deep-translator`)

### Command-Line Arguments
- `--resx-directory <directory>`: Specifies the path to the `.resx` files directory.
- `--exclude-languages <languages>`: Comma-separated list of languages to exclude (e.g., `fr,de`).
- `--force`: Translates all entries regardless of existing values.
  - **Example:**
    ```sh
    python main.py --force --resx-directory /path/to/resx --exclude-languages "es,it"
    ```
- `--new-only`: Translates only missing or new entries.
  - **Example:**
    ```sh
    python main.py --new-only --resx-directory /path/to/resx --exclude-languages "fr,de"
    ```
- `--workers <n>`: Number of parallel translation workers (default: `8`). Translation
  requests run concurrently across all languages, while each output file is still built
  and written once on a single thread, so the generated files never get mixed up. Lower
  this (e.g. `4`) if Google Translate starts rate-limiting.
  - **Example:**
    ```sh
    python main.py --new-only --resx-directory /path/to/resx --workers 4
    ```

### TypeScript i18n support

Besides `.resx` files, the script can translate a **TypeScript i18n file** that
keeps every language in one inline dictionary object:

```ts
export type Lang = "en" | "hu" | "zh" | "ru";

const DICTS: Record<Lang, Dict> = {
  en: {
    "toolbar.refresh": "Refresh",
    "menu.createBranch": "Create branch {name}",
  },
  hu: {
    "toolbar.refresh": "Frissítés",
  },
  zh: { /* ... */ },
  ru: { /* ... */ },
};
```

#### How it works

1. The script locates the `const DICTS = { ... }` object literal in the file
   (the declaration may also be `let` / `var` and may carry a type annotation
   such as `: Record<Lang, Dict>`).
2. It splits the object into one dictionary per language, keeping key order.
3. The **source language** (`en` by default, configurable with
   `--i18n-source-lang`) is the reference. Every key that exists in the source
   is checked in the other languages.
   - `--new-only`: only keys that are missing (or empty) in a target language
     are translated.
   - `--force`: every key of every non-source language is re-translated.
4. `{placeholder}` interpolation tokens (used by the `t("key", { name })`
   helper) are **kept verbatim** — they are shielded before translation and
   restored afterwards, even if the translator changes their casing/spacing.
5. Language keys are mapped to Google Translate codes automatically
   (`zh` → `zh-CN`, `zh-tw` → `zh-TW`, `he` → `iw`, …).
6. Only the `DICTS` object literal is rewritten (using the source key order for
   every language). Imports, the `t()` function, types and everything else in
   the file stay untouched.
7. Progress is shown live as a percentage bar with the **last 4 translated
   lines** below it:
   ```
   [###############---------------]  52.3%  (130/248)
     (zh) settings.theme: Theme --> 主题
     (ru) toolbar.push: ⇧ Push --> ⇧ Толкать
   ```

#### Command-line arguments

- `--i18n-file <path>`: Path to the `.ts` file that contains the `DICTS` object.
- `--i18n-source-lang <lang>`: Source language key inside `DICTS` (default `en`).
- `--workers <n>`: Parallel translation workers (default `8`). All missing keys across
  every language are translated concurrently; the `DICTS` object is then rebuilt and
  written once, so the file stays consistent.
- Use together with `--new-only` **or** `--force`, and optionally
  `--exclude-languages` (comma-separated language keys to skip, e.g. languages
  you maintain by hand).

#### Examples

Fill in only the missing keys for every language except `ru`:

```sh
python3 main.py --new-only \
  --i18n-file /path/to/project/packages/graph-webview/src/i18n.ts \
  --exclude-languages "ru"
```

Re-translate everything, but keep the hand-written `en` and `hu` dictionaries:

```sh
python3 main.py --force \
  --i18n-file /path/to/project/packages/graph-webview/src/i18n.ts \
  --exclude-languages "hu"
```

You can also use the interactive menu (options **3** and **4** cover the
TypeScript i18n file).

> On macOS use `python3` (and install the dependency with
> `pip3 install deep-translator --break-system-packages` if needed).

---

## Magyar

### Leírás
Ez a Python szkript automatikusan lefordítja a `.resx` erőforrásfájlokat egy projekt számára. Az alap `AppRes.resx` fájl alapján létrehozza vagy frissíti a többi nyelvi `.resx` fájlt a könyvtárban, és a hiányzó vagy elavult bejegyzéseket a Google Fordító segítségével lefordítja. Használható interaktív menüből vagy parancssori argumentumokkal. A felhasználók megadhatják a kizárni kívánt nyelveket.

### Működés
1. A szkript ellenőrzi az `AppRes.resx` fájl létezését.
2. Bejárja az összes `.resx` fájlt, kivéve a megadott nyelveket.
3. Betölti a meglévő fordításokat, vagy új `.resx` fájlt hoz létre.
4. A hiányzó vagy elavult bejegyzéseket a Google Fordítóval lefordítja.
5. A lefordított szövegeket beilleszti a megfelelő `.resx` fájlokba.
6. A szkript interaktív menüből vagy parancssorból is futtatható.

### Fordítás és futtatás

#### Linux
1. Telepítsd a Python 3-at:
   ```sh
   sudo apt install python3
   ```
2. Telepítsd a függőségeket:
   ```sh
   pip install deep-translator
   ```
3. Futtasd a szkriptet:
   ```sh
   python3 main.py --new-only --resx-directory /path/to/resx --exclude-languages "fr,de"
   ```
4. Hozz létre egy futtatható fájlt:
   ```sh
   pyinstaller --onefile --console --hidden-import=deep_translator.main main.py
   ```

#### Windows
1. Telepítsd a Python 3-at ([Python letöltés](https://www.python.org/downloads/)).
2. Telepítsd a függőségeket:
   ```cmd
   pip install deep-translator
   ```
3. Futtasd a szkriptet:
   ```cmd
   python main.py --new-only --resx-directory C:\path\to\resx --exclude-languages "fr,de"
   ```
4. Hozz létre egy futtatható fájlt:
   ```cmd
   pyinstaller --onefile --console --hidden-import=deep_translator.main main.py
   ```

#### macOS
1. Telepítsd a Python 3-at. Használhatod a hivatalos telepítőt a [Python letöltés](https://www.python.org/downloads/) oldalról, vagy a Homebrew-t:
   ```sh
   brew install python
   ```
2. Telepítsd a függőségeket:
   ```sh
   pip3 install deep-translator
   ```
3. Futtasd a szkriptet:
   ```sh
   python3 main.py --new-only --resx-directory /path/to/resx --exclude-languages "fr,de"
   ```
4. Hozz létre egy futtatható fájlt:
   ```sh
   pyinstaller --onefile --console --hidden-import=deep_translator.main main.py
   ```

### Függőségek
- `deep-translator` (telepíthető `pip install deep-translator` paranccsal)

### Parancssori argumentumok
- `--resx-directory <könyvtár>`: Az `.resx` fájlokat tartalmazó könyvtár elérési útja.
- `--exclude-languages <nyelvek>`: Kizárt nyelvek vesszővel elválasztott listája (pl. `fr,de`).
- `--force`: Az összes bejegyzést lefordítja, még ha már léteznek is.
  - **Példa:**
    ```sh
    python main.py --force --resx-directory /path/to/resx --exclude-languages "es,it"
    ```
- `--new-only`: Csak az új vagy hiányzó bejegyzéseket fordítja le.
  - **Példa:**
    ```sh
    python main.py --new-only --resx-directory /path/to/resx --exclude-languages "fr,de"
    ```
- `--workers <n>`: A párhuzamos fordító szálak száma (alapértelmezés: `8`). A fordítási
  kérések az összes nyelvre egyszerre futnak, de minden kimeneti fájl továbbra is egyetlen
  szálon, egyszer épül fel és íródik ki, így a generált fájlok soha nem keverednek össze.
  Csökkentsd (pl. `4`), ha a Google Fordító rate-limitelni kezd.
  - **Példa:**
    ```sh
    python main.py --new-only --resx-directory /path/to/resx --workers 4
    ```

### TypeScript i18n támogatás

A `.resx` fájlok mellett a szkript egy **TypeScript i18n fájlt** is le tud
fordítani, amely az összes nyelvet egyetlen soron belüli szótárobjektumban
tartja:

```ts
export type Lang = "en" | "hu" | "zh" | "ru";

const DICTS: Record<Lang, Dict> = {
  en: {
    "toolbar.refresh": "Refresh",
    "menu.createBranch": "Create branch {name}",
  },
  hu: {
    "toolbar.refresh": "Frissítés",
  },
  zh: { /* ... */ },
  ru: { /* ... */ },
};
```

#### Működés

1. A szkript megkeresi a `const DICTS = { ... }` objektumliterált a fájlban
   (lehet `let` / `var` is, és lehet rajta típusannotáció, pl.
   `: Record<Lang, Dict>`).
2. Az objektumot nyelvenként külön szótárra bontja, a kulcssorrendet megtartva.
3. A **forrásnyelv** (alapból `en`, a `--i18n-source-lang` kapcsolóval
   állítható) a referencia. A forrásban lévő minden kulcsot ellenőriz a többi
   nyelvben.
   - `--new-only`: csak a hiányzó (vagy üres) kulcsokat fordítja le az adott
     nyelvben.
   - `--force`: minden nem-forrásnyelv minden kulcsát újrafordítja.
4. A `{placeholder}` tokenek (amiket a `t("kulcs", { name })` hívás használ)
   **érintetlenül maradnak** – fordítás előtt védetté teszi, utána visszaállítja
   őket, még akkor is, ha a fordító megváltoztatja a kis-/nagybetűt vagy a
   szóközöket.
5. A nyelvi kulcsokat automatikusan Google Translate kódokra képezi le
   (`zh` → `zh-CN`, `zh-tw` → `zh-TW`, `he` → `iw`, …).
6. Csak a `DICTS` objektumliterál íródik újra (minden nyelvnél a forrás
   kulcssorrendjével). Az importok, a `t()` függvény, a típusok és minden más a
   fájlban változatlan marad.
7. A folyamat élőben látszik: százalékos csík, alatta a **4 legutóbbi lefordított
   sor**:
   ```
   [###############---------------]  52.3%  (130/248)
     (zh) settings.theme: Theme --> 主题
     (ru) toolbar.push: ⇧ Push --> ⇧ Толкать
   ```

#### Parancssori argumentumok

- `--i18n-file <útvonal>`: A `DICTS` objektumot tartalmazó `.ts` fájl elérési útja.
- `--i18n-source-lang <nyelv>`: A forrásnyelv kulcsa a `DICTS`-ben (alapértelmezés: `en`).
- `--workers <n>`: Párhuzamos fordító szálak száma (alapértelmezés: `8`). Az összes nyelv
  összes hiányzó kulcsa egyszerre fordul le; a `DICTS` objektum ezután egyszer épül újra és
  íródik ki, így a fájl konzisztens marad.
- A `--new-only` **vagy** `--force` kapcsolóval együtt használandó, opcionálisan
  a `--exclude-languages` kapcsolóval (vesszővel elválasztott nyelvi kulcsok,
  amiket ki kell hagyni – pl. amiket kézzel karbantartasz).

#### Példák

Csak a hiányzó kulcsok pótlása minden nyelvre, kivéve `ru`:

```sh
python3 main.py --new-only \
  --i18n-file /path/to/project/packages/graph-webview/src/i18n.ts \
  --exclude-languages "ru"
```

Minden újrafordítása, de a kézzel írt `en` és `hu` szótár megtartása:

```sh
python3 main.py --force \
  --i18n-file /path/to/project/packages/graph-webview/src/i18n.ts \
  --exclude-languages "hu"
```

Az interaktív menü is használható (a **3.** és **4.** opció a TypeScript i18n
fájlt kezeli).

> macOS-en `python3` a parancs (és ha kell, a függőség:
> `pip3 install deep-translator --break-system-packages`).
