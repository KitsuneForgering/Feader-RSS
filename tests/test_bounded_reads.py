"""Static guard: user-editable files must never be read without a byte ceiling.

The panel lives in the persistent shell, and the Go helper reads files that
users import, restore or edit by hand. Reading one of those whole before any
size check lets an oversized file exhaust memory before JSON/XML parsing and
the feed limits apply. These checks keep that class of bug from coming back:

* QML: a FileView may only write and watch. It must set `preload: false` and
  nothing may call text()/data()/reload() on it or react to onLoaded; reads
  go through the bounded `boundedReadCommand` process instead.
* Go: os.ReadFile is banned outside tests (use localfile.ReadCapped), and
  io.ReadAll is only allowed over an io.LimitReader.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]


def qml_sources():
    return {path.name: path.read_text() for path in sorted(ROOT.glob("*.qml"))}


def go_sources():
    return {
        str(path.relative_to(ROOT)): path.read_text()
        for path in sorted(ROOT.rglob("*.go"))
        if not path.name.endswith("_test.go")
    }


def file_view_blocks(source):
    """Yield (id, body) for each FileView, matched by brace depth."""
    for match in re.finditer(r"\bFileView\s*\{", source):
        depth, end = 0, match.end() - 1
        for end in range(match.end() - 1, len(source)):
            depth += {"{": 1, "}": -1}.get(source[end], 0)
            if depth == 0:
                break
        body = source[match.start():end + 1]
        ident = re.search(r"\n\s*id:\s*(\w+)", body)
        yield (ident.group(1) if ident else "<anonymous>"), body


class QmlBoundedReadTests(unittest.TestCase):
    def test_file_views_never_load_contents(self):
        for name, source in qml_sources().items():
            for ident, body in file_view_blocks(source):
                with self.subTest(file=name, view=ident):
                    self.assertRegex(body, r"\n\s*preload:\s*false\b",
                                     "FileView must not preload the whole file")
                    self.assertNotRegex(body, r"\bonLoaded\s*:")
                    self.assertNotRegex(body, r"\b(text|data|reload)\(\)")
                    self.assertNotRegex(body, r"\bblockLoading\s*:\s*true")
                    self.assertNotRegex(source, rf"\b{ident}\.(text|data|reload)\(")

    def test_panel_reads_settings_through_the_bounded_process(self):
        panel = qml_sources()["Panel.qml"]
        self.assertRegex(panel, r"readonly property int maxSettingsFileBytes: \d+")
        for path in ("root.configPath", "root.statePath"):
            self.assertIn(f"command: root.boundedReadCommand({path}, root.maxSettingsFileBytes)", panel)

    def test_guard_detects_an_unbounded_file_view(self):
        bad = "Item {\n  FileView {\n    id: cfg\n    path: p\n    onLoaded: load(text())\n  }\n}\n"
        (ident, body), = file_view_blocks(bad)
        self.assertEqual(ident, "cfg")
        self.assertNotRegex(body, r"\n\s*preload:\s*false\b")
        self.assertRegex(body, r"\bonLoaded\s*:")


class GoBoundedReadTests(unittest.TestCase):
    def test_no_unbounded_file_reads(self):
        for name, source in go_sources().items():
            with self.subTest(file=name):
                self.assertNotRegex(source, r"\bos\.ReadFile\(",
                                    "use localfile.ReadCapped instead of os.ReadFile")
                for line in source.splitlines():
                    if re.search(r"\bio\.ReadAll\(", line):
                        self.assertRegex(line, r"io\.ReadAll\(io\.LimitReader\(",
                                         f"io.ReadAll without io.LimitReader: {line.strip()}")


if __name__ == "__main__":
    unittest.main()
