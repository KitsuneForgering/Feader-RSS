"""Every GitHub Actions workflow must be valid YAML.

A workflow GitHub cannot parse fails with zero jobs, so CI never gets far
enough to report the problem itself; this catches it locally. (E.g. an
unquoted `run:` value containing `: ` is read as a nested mapping.)
"""
import unittest
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - depends on the local environment
    yaml = None

WORKFLOWS = sorted((Path(__file__).parents[1] / ".github" / "workflows").glob("*.yml"))


@unittest.skipIf(yaml is None, "PyYAML is required to parse the workflows")
class WorkflowSyntaxTests(unittest.TestCase):
    def test_workflows_parse_and_every_step_is_well_formed(self):
        self.assertTrue(WORKFLOWS)
        for path in WORKFLOWS:
            with self.subTest(workflow=path.name):
                workflow = yaml.safe_load(path.read_text())
                self.assertIsInstance(workflow.get("jobs"), dict)
                for job in workflow["jobs"].values():
                    for step in job.get("steps", []):
                        self.assertTrue("run" in step or "uses" in step, step)
                        if "run" in step:
                            self.assertIsInstance(step["run"], str, step)


if __name__ == "__main__":
    unittest.main()
