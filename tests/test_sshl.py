"""Run with: python3 -m unittest discover -s tests"""
import importlib.machinery
import importlib.util
import io
import os
import unittest
from contextlib import redirect_stderr, redirect_stdout

HERE = os.path.dirname(__file__)
SCRIPT = os.path.join(HERE, "..", "sshl")
FIXTURE = os.path.join(HERE, "fixtures", "config")

loader = importlib.machinery.SourceFileLoader("sshl", SCRIPT)
spec = importlib.util.spec_from_loader("sshl", loader)
sshl = importlib.util.module_from_spec(spec)
loader.exec_module(sshl)


def run(*args):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = sshl.main(["-F", FIXTURE, *args])
    return code, out.getvalue(), err.getvalue()


def host_lines(text):
    return [line.split()[0] for line in text.splitlines() if line.startswith("  ") and not line.strip().startswith("ALIASES")]


class Parsing(unittest.TestCase):
    def setUp(self):
        self.hosts = sshl.parse(sshl.read_lines(FIXTURE, set()))
        self.by = {h["names"][0]: h for h in self.hosts}

    def test_wildcard_host_is_not_listed(self):
        self.assertNotIn("*", self.by)

    def test_first_value_wins_like_ssh(self):
        self.assertEqual(self.by["staging"]["user"], "app")

    def test_include_is_expanded_and_match_blocks_are_ignored(self):
        self.assertEqual(self.by["prod"]["user"], "app")

    def test_sections_come_from_headers_after_a_rule(self):
        self.assertEqual(self.by["nas"]["section"], "Home lab")
        self.assertEqual(self.by["prod"]["section"], "Work")

    def test_via(self):
        self.assertEqual(sshl.via(self.by["web"]), "jump pve")
        self.assertEqual(sshl.via(self.by["pve-remote"]), "cloudflared")
        self.assertEqual(sshl.via(self.by["nas"]), "")


class Ordering(unittest.TestCase):
    def test_by_vm_id_then_same_address_then_the_rest(self):
        code, out, _ = run()
        self.assertEqual(code, 0)
        self.assertEqual(
            host_lines(out),
            ["proxmox", "pve-admin", "web", "nas", "pve-remote", "prod", "staging"],
        )


class Output(unittest.TestCase):
    def test_header_row_and_no_colour_when_not_a_tty(self):
        _, out, _ = run()
        self.assertIn("ALIASES", out)
        self.assertNotIn("\033[", out)

    def test_filter_matches_alias_address_or_section(self):
        self.assertEqual(host_lines(run("work")[1]), ["prod", "staging"])
        self.assertEqual(host_lines(run("192.168.20")[1]), ["web"])

    def test_no_match_is_an_error(self):
        code, _, err = run("nothing-like-this")
        self.assertEqual(code, 1)
        self.assertIn("no host matches", err)

    def test_missing_config(self):
        err = io.StringIO()
        with redirect_stderr(err):
            self.assertEqual(sshl.main(["-F", "/nonexistent/config"]), 1)


if __name__ == "__main__":
    unittest.main()
