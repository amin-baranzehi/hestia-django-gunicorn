import unittest
from cli import build_parser


class TestCliParser(unittest.TestCase):
    def setUp(self):
        self.parser = build_parser()

    def test_install_templates_command(self):
        args = self.parser.parse_args(["install-templates"])
        self.assertEqual(args.command, "install-templates")

    def test_install_template_alias(self):
        args = self.parser.parse_args(["install-template"])
        self.assertEqual(args.command, "install-template")

    def test_install_template_with_extra_args(self):
        args = self.parser.parse_args(["install-template", "amin"])
        self.assertEqual(args.command, "install-template")
        self.assertEqual(args.extra, ["amin"])


if __name__ == "__main__":
    unittest.main()

