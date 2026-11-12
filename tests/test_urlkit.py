import contextlib
import io
import json
import os
import unittest
from unittest import mock

import urlkit as uk

FULL = "https://user:pass@Example.COM:8443/a/b?q=hello%20world&lang=en#docs"

ROUNDTRIP = [
    "https://example.com",
    FULL,
    "http://example.com:80/a/./b/../c",
    "http://[2001:db8::1]:8080/p?x=1",
    "https://x.io/path%2Fwith%2Fescapes?a=%2B&b=c%26d#f%20g",
    "http://x/?a=1&a=2&b=&flag",
    "mailto:user@example.com",
    "https://example.com/a/b/c?z=1&a=2&m=3#top",
    "ftp://ftp.example.org/pub/file.txt",
    "http://x/caf%C3%A9?q=na%C3%AFve",
]


def run_cli(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = uk.main(argv)
    return code, out.getvalue(), err.getvalue()


class FakeTTY(io.StringIO):
    def isatty(self):
        return True


class ParseTests(unittest.TestCase):
    def test_parse_full(self):
        p = uk.parse_url(FULL)
        self.assertEqual(p["scheme"], "https")
        self.assertEqual(p["userinfo"], "user:pass")
        self.assertEqual(p["host"], "Example.COM")
        self.assertEqual(p["port"], 8443)
        self.assertEqual(p["path"], "/a/b")
        self.assertEqual(p["query"], [["q", "hello world"], ["lang", "en"]])
        self.assertEqual(p["fragment"], "docs")

    def test_parse_minimal(self):
        p = uk.parse_url("http://example.com")
        self.assertEqual(p, {"scheme": "http", "userinfo": None,
                             "host": "example.com", "port": None, "path": "",
                             "query": [], "fragment": ""})

    def test_parse_query_duplicates_and_blanks(self):
        p = uk.parse_url("http://x/?a=1&a=2&b=&flag")
        self.assertEqual(p["query"], [["a", "1"], ["a", "2"], ["b", ""], ["flag", ""]])

    def test_parse_ipv6(self):
        p = uk.parse_url("http://[2001:db8::1]:8080/p")
        self.assertEqual(p["host"], "2001:db8::1")
        self.assertEqual(p["port"], 8080)

    def test_parse_no_authority_mailto(self):
        p = uk.parse_url("mailto:user@example.com")
        self.assertEqual(p["scheme"], "mailto")
        self.assertIsNone(p["host"])
        self.assertEqual(p["path"], "user@example.com")

    def test_parse_decodes_query(self):
        p = uk.parse_url("http://x/?q=a%2Bb%26c%3Dd&plus=a+b")
        self.assertEqual(p["query"], [["q", "a+b&c=d"], ["plus", "a b"]])

    def test_parse_preserves_case_and_raw_path(self):
        p = uk.parse_url("HTTP://Example.COM/A%2fB")
        self.assertEqual(p["scheme"], "http")  # urlsplit lowercases the scheme
        self.assertEqual(p["host"], "Example.COM")
        self.assertEqual(p["path"], "/A%2fB")


class ValidationTests(unittest.TestCase):
    def test_empty_and_whitespace(self):
        for bad in ("", "   ", "\t"):
            with self.subTest(bad=bad):
                with self.assertRaises(uk.BadUrl):
                    uk.parse_url(bad)

    def test_missing_scheme(self):
        for bad in ("example.com/x", "/just/path", "1http://x", "://x"):
            with self.subTest(bad=bad):
                with self.assertRaises(uk.BadUrl):
                    uk.parse_url(bad)

    def test_empty_host(self):
        for bad in ("http://", "https://?q=1", "http://user@/"):
            with self.subTest(bad=bad):
                with self.assertRaises(uk.BadUrl):
                    uk.parse_url(bad)

    def test_bad_port(self):
        for bad in ("http://x:abc/", "http://x:99999/", "http://x:-1/"):
            with self.subTest(bad=bad):
                with self.assertRaises(uk.BadUrl):
                    uk.parse_url(bad)

    def test_bad_ipv6(self):
        for bad in ("http://[::1/", "http://::1/"):
            with self.subTest(bad=bad):
                with self.assertRaises(uk.BadUrl):
                    uk.parse_url(bad)

    def test_control_chars(self):
        for bad in ("http://x/a\tb", "http://x/a\nb", "http://x/\x00"):
            with self.subTest(bad=bad):
                with self.assertRaises(uk.BadUrl):
                    uk.parse_url(bad)


class NormalizeTests(unittest.TestCase):
    def test_lowercases_scheme_and_host_only(self):
        self.assertEqual(uk.normalize_url("HTTP://Example.COM/Path"),
                         "http://example.com/Path")

    def test_drops_default_ports(self):
        cases = [("http://x:80/", "http://x/"),
                 ("https://x:443", "https://x"),
                 ("http://x:8080/", "http://x:8080/"),
                 ("https://x:80/", "https://x:80/")]
        for src, want in cases:
            with self.subTest(src=src):
                self.assertEqual(uk.normalize_url(src), want)

    def test_dot_segments(self):
        cases = [("http://x/a/./b/../c", "http://x/a/c"),
                 ("http://x/a/b/../../c", "http://x/c"),
                 ("http://x/a/b/..", "http://x/a/"),
                 ("http://x/../a", "http://x/a"),
                 ("http://x/.", "http://x/"),
                 ("http://x/..", "http://x/")]
        for src, want in cases:
            with self.subTest(src=src):
                self.assertEqual(uk.normalize_url(src), want)

    def test_encodes_spaces(self):
        self.assertEqual(uk.normalize_url("http://x/a b?greeting=hello world"),
                         "http://x/a%20b?greeting=hello%20world")

    def test_encodes_non_ascii(self):
        self.assertEqual(uk.normalize_url("http://x/caf\u00e9?q=na\u00efve"),
                         "http://x/caf%C3%A9?q=na%C3%AFve")

    def test_keeps_existing_escapes(self):
        src = "http://x/a%2Fb?q=a%20b&c=d+e"
        self.assertEqual(uk.normalize_url(src), src)

    def test_drops_empty_fragment_keeps_nonempty(self):
        self.assertEqual(uk.normalize_url("http://x/#"), "http://x/")
        self.assertEqual(uk.normalize_url("http://x/#top"), "http://x/#top")

    def test_query_order_preserved(self):
        src = "http://x/?z=1&a=2&m=3"
        self.assertEqual(uk.normalize_url(src), src)

    def test_idempotent(self):
        messy = "HTTP://User:Pass@Example.COM:80/a/./b/../c?greeting=hello world&lang=en#"
        once = uk.normalize_url(messy)
        self.assertEqual(once, "http://User:Pass@example.com/a/c?greeting=hello%20world&lang=en")
        self.assertEqual(uk.normalize_url(once), once)

    def test_ipv6_and_default_port(self):
        self.assertEqual(uk.normalize_url("HTTPS://[2001:DB8::1]:443/p"),
                         "https://[2001:db8::1]/p")


class BuildTests(unittest.TestCase):
    def test_build_basic(self):
        url = uk.build_url({"scheme": "https", "host": "example.com", "path": "/a",
                            "query": [["q", "hello world"]], "fragment": "top"})
        self.assertEqual(url, "https://example.com/a?q=hello+world#top")

    def test_build_port_and_path_slash(self):
        url = uk.build_url({"scheme": "http", "host": "x", "port": 8443, "path": "a/b"})
        self.assertEqual(url, "http://x:8443/a/b")

    def test_build_ipv6(self):
        for host in ("2001:db8::1", "[2001:db8::1]"):
            with self.subTest(host=host):
                url = uk.build_url({"scheme": "http", "host": host, "path": "/"})
                self.assertEqual(url, "http://[2001:db8::1]/")

    def test_build_encodes_query_and_fragment(self):
        url = uk.build_url({"scheme": "http", "host": "x",
                            "query": [["q", "a b&c=d"]], "fragment": "a b"})
        self.assertEqual(url, "http://x?q=a+b%26c%3Dd#a%20b")

    def test_build_userinfo(self):
        url = uk.build_url({"scheme": "http", "host": "x", "userinfo": "user:p@ss"})
        self.assertEqual(url, "http://user:p%40ss@x")

    def test_build_invalid(self):
        cases = [{"scheme": "https", "host": ""},
                 {"scheme": "1http", "host": "x"},
                 {"scheme": "http", "host": "x", "port": 99999},
                 {"scheme": "http", "host": "a/b"},
                 {"scheme": "http", "host": "a b"},
                 {"scheme": "http", "host": "[not-ipv6]"}]
        for parts in cases:
            with self.subTest(parts=parts):
                with self.assertRaises(uk.BadUrl):
                    uk.build_url(parts)


class RoundTripTests(unittest.TestCase):
    def test_roundtrip_representative(self):
        for src in ROUNDTRIP:
            with self.subTest(src=src):
                parts = uk.parse_url(src)
                rebuilt = uk.build_url(parts)
                self.assertEqual(uk.parse_url(rebuilt), parts)

    def test_roundtrip_query_pairs_survive_encoding(self):
        parts = uk.parse_url("http://x/?a=1&a=2&b=&flag&q=a%2Bb")
        rebuilt = uk.build_url(parts)
        self.assertEqual(uk.parse_url(rebuilt)["query"], parts["query"])


class QueryEditTests(unittest.TestCase):
    def test_set_replaces_in_place(self):
        self.assertEqual(uk.modify_query("http://x/?a=1&b=2&a=3", ["a=9"]),
                         "http://x/?a=9&b=2")

    def test_set_appends_new_keys_in_order(self):
        self.assertEqual(uk.modify_query("http://x/?a=1", ["b=2", "c=3"]),
                         "http://x/?a=1&b=2&c=3")

    def test_remove_all_occurrences(self):
        self.assertEqual(uk.modify_query("http://x/?a=1&b=2&a=3", [], ["a"]),
                         "http://x/?b=2")

    def test_untouched_params_keep_raw_encoding(self):
        self.assertEqual(uk.modify_query("http://x/?keep=a%20b&drop=1", [], ["drop"]),
                         "http://x/?keep=a%20b")

    def test_set_encodes_values(self):
        self.assertEqual(uk.modify_query("http://x/", ["q=hello world&x"]),
                         "http://x/?q=hello+world%26x")

    def test_remove_beats_set(self):
        self.assertEqual(uk.modify_query("http://x/?a=1", ["a=2"], ["a"]),
                         "http://x/")

    def test_no_flags_keeps_url(self):
        src = "http://x/?a=1&b=2"
        self.assertEqual(uk.modify_query(src), src)

    def test_path_and_fragment_preserved(self):
        self.assertEqual(uk.modify_query("http://x/p?a=1#f", ["a=2"]),
                         "http://x/p?a=2#f")

    def test_empty_query_gains_params(self):
        self.assertEqual(uk.modify_query("http://x", ["a=1"]), "http://x?a=1")


class CliTests(unittest.TestCase):
    def test_cli_parse_json(self):
        code, out, err = run_cli(["--json", "parse", FULL])
        self.assertEqual(code, 0)
        self.assertEqual(err, "")
        self.assertEqual(json.loads(out), uk.parse_url(FULL))

    def test_cli_parse_text(self):
        code, out, _ = run_cli(["--no-color", "parse", FULL])
        self.assertEqual(code, 0)
        self.assertIn("scheme", out)
        self.assertIn("Example.COM", out)
        self.assertIn("hello world", out)
        self.assertNotIn("\x1b", out)

    def test_cli_normalize_json(self):
        code, out, _ = run_cli(["--json", "normalize", "HTTP://Example.COM:80/a/../b"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["normalized"], "http://example.com/b")
        self.assertTrue(data["changed"])

    def test_cli_query_json(self):
        code, out, _ = run_cli(["--json", "query", "http://x/?a=1&b=2",
                                "--set", "a=9", "--remove", "b"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["url"], "http://x/?a=9")
        self.assertEqual(data["query"], [["a", "9"]])

    def test_cli_build(self):
        code, out, _ = run_cli(["build", "--scheme", "https", "--host", "example.com",
                                "--path", "/x", "--query", "q=1"])
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "https://example.com/x?q=1")

    def test_cli_bad_url_exit2(self):
        for argv in (["parse", ""], ["normalize", "http://"], ["query", "nope"],
                     ["build", "--scheme", "http", "--host", ""]):
            with self.subTest(argv=argv):
                code, out, err = run_cli(argv)
                self.assertEqual(code, 2)
                self.assertEqual(out, "")
                self.assertIn("urlkit:", err)

    def test_cli_version(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            with self.assertRaises(SystemExit) as cm:
                uk.main(["--version"])
        self.assertEqual(cm.exception.code, 0)
        self.assertEqual(out.getvalue().strip(), "urlkit " + uk.__version__)

    def test_cli_json_flag_after_subcommand(self):
        code, out, _ = run_cli(["parse", FULL, "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["host"], "Example.COM")

    def test_cli_no_subcommand_exit2(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            with self.assertRaises(SystemExit) as cm:
                uk.main([])
        self.assertEqual(cm.exception.code, 2)


class ColorTests(unittest.TestCase):
    def test_colorize_on_off(self):
        self.assertEqual(uk.colorize("x", "green", True), "\x1b[32mx\x1b[0m")
        self.assertEqual(uk.colorize("x", "green", False), "x")

    def test_render_parse_ansi(self):
        parts = uk.parse_url(FULL)
        self.assertIn("\x1b[", uk.render_parse(parts, True))
        self.assertNotIn("\x1b", uk.render_parse(parts, False))

    def test_color_enabled_gates(self):
        self.assertTrue(uk.color_enabled(False, FakeTTY()))
        self.assertFalse(uk.color_enabled(True, FakeTTY()))
        self.assertFalse(uk.color_enabled(False, io.StringIO()))
        with mock.patch.dict(os.environ, {"NO_COLOR": "1"}):
            self.assertFalse(uk.color_enabled(False, FakeTTY()))


if __name__ == "__main__":
    unittest.main()