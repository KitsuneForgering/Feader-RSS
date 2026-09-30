"""Runs qmllint over every shipped QML file.

The Omarchy shell modules (qs.Commons, qs.Ui, ...) only exist inside the
running shell, so qmllint cannot resolve them here. Warnings caused by that
are expected and filtered out by category; every other warning (syntax
errors, duplicate bindings, missing members on real Qt types, eval, ...)
fails the test.

qmllint is looked up in $QMLLINT, then PATH (qmllint, qmllint6,
pyside6-qmllint), then /usr/lib/qt6/bin. Set FEADER_REQUIRE_QMLLINT=1 (CI
does) to fail instead of skipping when it is not installed.
"""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
QML_FILES = sorted(ROOT.glob("*.qml"))

# Categories that only fire because the shell's own modules are unavailable
# outside it. They say nothing about this plugin's code.
ENVIRONMENT_CATEGORIES = {
    "import",                     # qs.Commons / qs.Ui cannot be found
    "unqualified",                # ids and members those modules provide
    "unresolved-type",            # types those modules provide
    "inheritance-cycle",          # Panel.qml's root is the shell's Panel
    "required",                   # required properties of shell delegates
    "signal-handler-parameters",  # Quickshell.Io signal types not exported
}


def find_qmllint():
    candidates = [os.environ.get("QMLLINT")]
    candidates += [shutil.which(name) for name in ("qmllint", "qmllint6", "pyside6-qmllint")]
    candidates += ["/usr/lib/qt6/bin/qmllint", "/usr/lib64/qt6/bin/qmllint"]
    for candidate in candidates:
        if candidate and os.access(candidate, os.X_OK):
            return candidate
    return None


QMLLINT = find_qmllint()


def is_environment_noise(warning):
    category = warning.get("id")
    if category in ENVIRONMENT_CATEGORIES:
        return True
    # Members accessed through a shell-provided object typed as a bare
    # QObject (e.g. BarWidget's `panel`). A missing member on a real Qt type
    # such as MouseArea is a genuine bug and is not excused.
    return category == "missing-property" and 'on type "QObject"' in warning.get("message", "")


def lint(paths):
    """Return (exit code, [(file, warning)]) for the given QML files."""
    with tempfile.TemporaryDirectory() as tmp:
        report = Path(tmp) / "qmllint.json"
        done = subprocess.run([QMLLINT, "--json", str(report), *map(str, paths)],
                              capture_output=True, text=True, timeout=120)
        if not report.exists():
            raise AssertionError(f"qmllint produced no report: {done.stderr}")
        data = json.loads(report.read_text())
    warnings = [(Path(f["filename"]).name, w) for f in data["files"] for w in f["warnings"]]
    return done.returncode, warnings


def problems(warnings):
    return [
        f"{name}:{w.get('line')}:{w.get('column')}: {w.get('message')} [{w.get('id')}]"
        for name, w in warnings
        if w.get("type") != "info" and not is_environment_noise(w)
    ]


class QmlLintTests(unittest.TestCase):
    def setUp(self):
        if QMLLINT is None:
            if os.environ.get("FEADER_REQUIRE_QMLLINT") == "1":
                self.fail("qmllint is required (FEADER_REQUIRE_QMLLINT=1) but was not found")
            self.skipTest("qmllint is not installed")

    def test_shipped_qml_has_no_lint_problems(self):
        self.assertTrue(QML_FILES, "no QML files found")
        code, warnings = lint(QML_FILES)
        found = problems(warnings)
        self.assertEqual(found, [], "qmllint reported:\n" + "\n".join(found))
        self.assertNotEqual(code, 255, "qmllint could not parse the QML files")

    def test_filter_still_catches_real_mistakes(self):
        # Guards the noise filter itself: if it ever grows permissive enough
        # to swallow these, the test above would pass vacuously.
        cases = {
            "syntax.qml": "import QtQuick\nItem {\n  function f() { var x = ; }\n}\n",
            "member.qml": "import QtQuick\nItem {\n  MouseArea { id: area }\n  opacity: area.hovered ? 1 : 0\n}\n",
            "duplicate.qml": "import QtQuick\nItem {\n  width: 1\n  width: 2\n}\n",
        }
        with tempfile.TemporaryDirectory() as tmp:
            for name, source in cases.items():
                path = Path(tmp) / name
                path.write_text(source)
                with self.subTest(name):
                    _, warnings = lint([path])
                    self.assertNotEqual(problems(warnings), [])


if __name__ == "__main__":
    unittest.main()
