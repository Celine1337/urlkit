#!/usr/bin/env python3
"""urlkit - a small URL toolbox built on urllib.parse.

Subcommands: parse (split a URL into components), normalize (lowercase
scheme/host, drop default ports, resolve dot segments, percent-encode where
needed, drop empty fragment), build (assemble a URL from parts) and query
(edit query parameters in place). Single file, standard library only, no
network access. Python 3.9+.
"""

import argparse
import ipaddress
import json
import os
import re
import sys
from urllib.parse import (parse_qsl, quote, quote_plus, unquote_plus, urlencode,
                          urlsplit, urlunsplit)

__version__ = "1.0.0"

SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*$")
AUTHORITY_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*://")
PORT_RE = re.compile(r"^[0-9]+$")
ESCAPE_RE = re.compile(r"%[0-9A-Fa-f]{2}")

# RFC 3986 safe characters per component (unreserved a-z A-Z 0-9 - . _ ~ are
# never quoted by urllib.parse.quote).
PATH_SAFE = "!$&'()*+,;=:@/"
QUERY_SAFE = "!$&'()*+,;=:@/?"
FRAGMENT_SAFE = "!$&'()*+,;=:@/?"
USERINFO_SAFE = "!$&'()*+,;=:"

COLOR_CODES = {"red": "31", "green": "32", "yellow": "33", "cyan": "36",
               "bold": "1", "dim": "2", "label": "1;36"}


class BadUrl(ValueError):
    """Raised for empty or malformed input URLs (CLI exit code 2)."""


def pct_encode(s, safe):
    """Percent-encode characters that need it, keeping existing %XX escapes."""
    if not s:
        return s
    out, pos = [], 0
    for m in ESCAPE_RE.finditer(s):
        out.append(quote(s[pos:m.start()], safe=safe))
        out.append(m.group(0))
        pos = m.end()
    out.append(quote(s[pos:], safe=safe))
    return "".join(out)


def remove_dot_segments(path):
    """RFC 3986 5.2.4: resolve '.' and '..' segments, keep trailing slashes."""
    out = []
    while path:
        if path.startswith("../"):
            path = path[3:]
        elif path.startswith("./"):
            path = path[2:]
        elif path.startswith("/./"):
            path = "/" + path[3:]
        elif path == "/.":
            path = "/"
        elif path.startswith("/../"):
            path = "/" + path[4:]
            if out:
                out.pop()
        elif path == "/..":
            path = "/"
            if out:
                out.pop()
        elif path in (".", ".."):
            path = ""
        else:
            idx = path.find("/", 1 if path.startswith("/") else 0)
            if idx == -1:
                out.append(path)
                path = ""
            else:
                out.append(path[:idx])
                path = path[idx:]
    return "".join(out)


def split_netloc(netloc):
    """Split an authority into (userinfo, host, port); host has no brackets."""
    if not netloc:
        return None, None, None
    userinfo, sep, hostport = netloc.rpartition("@")
    if not sep:
        userinfo, hostport = None, netloc
    if hostport.startswith("["):
        end = hostport.find("]")
        if end < 0:
            raise BadUrl("unterminated IPv6 literal")
        host = hostport[1:end]
        try:
            ipaddress.IPv6Address(host)
        except ValueError:
            raise BadUrl("invalid IPv6 host %r" % host)
        rest = hostport[end + 1:]
        if rest and not rest.startswith(":"):
            raise BadUrl("malformed authority %r" % netloc)
        p = rest[1:]
    else:
        host, colon, p = hostport.rpartition(":")
        if not colon:
            host, p = hostport, ""
        elif ":" in host:
            raise BadUrl("IPv6 host must be bracketed")
    port = None
    if p:
        if not PORT_RE.match(p):
            raise BadUrl("invalid port %r" % p)
        port = int(p)
        if port > 65535:
            raise BadUrl("port out of range: %d" % port)
    if not host:
        raise BadUrl("empty host")
    return userinfo, host, port


def parse_url(text):
    """Parse a URL into components; raise BadUrl for empty/invalid input.

    Query is a list of [key, value] pairs, percent-decoded, order preserved.
    Host keeps its original case and has no IPv6 brackets; port is an int.
    """
    if not isinstance(text, str):
        raise BadUrl("URL must be a string")
    url = text.strip()
    if not url:
        raise BadUrl("empty URL")
    if any(ord(c) < 0x20 or ord(c) == 0x7F for c in url):
        raise BadUrl("control characters in URL")
    try:
        us = urlsplit(url)
    except ValueError as exc:
        raise BadUrl("malformed URL: %s" % exc)
    if not SCHEME_RE.match(us.scheme):
        raise BadUrl("missing or invalid scheme (expected e.g. https://...)")
    userinfo, host, port = split_netloc(us.netloc)
    if host is None and AUTHORITY_RE.match(url):
        raise BadUrl("empty host")
    pairs = [[k, v] for k, v in
             parse_qsl(us.query, keep_blank_values=True, separator="&")]
    return {"scheme": us.scheme, "userinfo": userinfo, "host": host,
            "port": port, "path": us.path, "query": pairs,
            "fragment": us.fragment}


def normalize_url(text):
    """Lowercase scheme+host, drop default ports, resolve dot segments,
    percent-encode where needed, drop an empty fragment. Order is kept."""
    parse_url(text)  # validation
    us = urlsplit(text.strip())
    scheme = us.scheme.lower()
    userinfo, host, port = split_netloc(us.netloc)
    if host is not None:
        host = host.lower()
        if ":" in host:
            host = "[" + host + "]"
    if (scheme == "http" and port == 80) or (scheme == "https" and port == 443):
        port = None
    netloc = ""
    if host is not None:
        netloc = host
        if port is not None:
            netloc += ":%d" % port
        if userinfo is not None:
            netloc = pct_encode(userinfo, USERINFO_SAFE) + "@" + netloc
    path = pct_encode(remove_dot_segments(us.path), PATH_SAFE)
    query = pct_encode(us.query, QUERY_SAFE)
    fragment = pct_encode(us.fragment, FRAGMENT_SAFE)
    return urlunsplit((scheme, netloc, path, query, fragment))


def build_url(parts):
    """Assemble a URL from a component dict (same shape as parse_url output).

    Query pairs are treated as decoded key/value strings and re-encoded.
    Raises BadUrl for invalid scheme, host or port.
    """
    scheme = (parts.get("scheme") or "").lower()
    if not SCHEME_RE.match(scheme):
        raise BadUrl("invalid scheme %r" % parts.get("scheme"))
    host = parts.get("host")
    port = parts.get("port")
    userinfo = parts.get("userinfo")
    path = parts.get("path") or ""
    pairs = parts.get("query") or []
    fragment = parts.get("fragment") or ""
    netloc = ""
    if host is not None:
        h = host.strip() if isinstance(host, str) else ""
        if not h:
            raise BadUrl("empty host")
        bracketed = h.startswith("[")
        if bracketed:
            if not h.endswith("]"):
                raise BadUrl("invalid IPv6 host %r" % host)
            h = h[1:-1]
        if bracketed or ":" in h:
            try:
                ipaddress.IPv6Address(h)
            except ValueError:
                raise BadUrl("invalid IPv6 host %r" % host)
            h = "[" + h + "]"
        if any(c in h for c in "/?#@") or any(c.isspace() for c in h):
            raise BadUrl("invalid host %r" % host)
        netloc = h
        if port is not None:
            if not isinstance(port, int) or not 0 <= port <= 65535:
                raise BadUrl("invalid port %r" % port)
            netloc += ":%d" % port
        if userinfo is not None:
            netloc = pct_encode(userinfo, USERINFO_SAFE) + "@" + netloc
    if path and netloc and not path.startswith("/"):
        path = "/" + path
    url = urlunsplit((scheme, netloc, pct_encode(path, PATH_SAFE),
                      urlencode([tuple(p) for p in pairs]),
                      pct_encode(fragment, FRAGMENT_SAFE)))
    parse_url(url)  # final validation
    return url


def split_kv(s):
    """Split a 'k=v' flag value on the first '='; a missing '=' means ''."""
    k, _, v = s.partition("=")
    return [k, v]


def modify_query(text, sets=(), removes=()):
    """Return the URL with its query edited, other params kept verbatim.

    --set k=v replaces k in place (first occurrence; later duplicates are
    dropped) or appends it in flag order. --remove k drops every occurrence
    and wins over --set for the same key.
    """
    parse_url(text)  # validation
    us = urlsplit(text.strip())
    set_pairs = [split_kv(s) for s in sets]
    set_map = {}
    for k, v in set_pairs:
        set_map[k] = v
    remove_set = set(removes)
    out, seen = [], set()
    for item in (us.query.split("&") if us.query else []):
        if not item:
            continue
        key = unquote_plus(item.partition("=")[0])
        if key in remove_set:
            continue
        if key in set_map:
            if key in seen:
                continue
            seen.add(key)
            out.append(quote_plus(key) + "=" + quote_plus(set_map[key]))
        else:
            out.append(item)
    for k, v in set_pairs:
        if k in seen or k in remove_set:
            continue
        seen.add(k)
        out.append(quote_plus(k) + "=" + quote_plus(v))
    return urlunsplit((us.scheme, us.netloc, us.path, "&".join(out), us.fragment))


def colorize(text, color, enabled):
    if not enabled:
        return text
    return "\x1b[%sm%s\x1b[0m" % (COLOR_CODES[color], text)


def color_enabled(no_color=False, stream=None):
    if stream is None:
        stream = sys.stdout
    return not no_color and not os.environ.get("NO_COLOR") and stream.isatty()


def render_parse(parts, color):
    def lab(name):
        return colorize(name.ljust(9), "label", color)

    def val(v):
        if v is None or v == "":
            return colorize("-", "dim", color)
        return str(v)

    lines = [lab("scheme") + " " + val(parts["scheme"]),
             lab("userinfo") + " " + val(parts["userinfo"]),
             lab("host") + " " + val(parts["host"]),
             lab("port") + " " + val(parts["port"]),
             lab("path") + " " + val(parts["path"])]
    pairs = parts["query"]
    if pairs:
        lines.append(lab("query") + " " + colorize(
            "%d pair%s" % (len(pairs), "" if len(pairs) == 1 else "s"), "dim", color))
        for k, v in pairs:
            shown = v if v != "" else colorize("(empty)", "dim", color)
            lines.append("  " + colorize(k, "green", color)
                         + colorize(" = ", "dim", color) + shown)
    else:
        lines.append(lab("query") + " " + val(None))
    lines.append(lab("fragment") + " " + val(parts["fragment"]))
    return "\n".join(lines)


def render_url(url, color):
    return colorize(url, "green", color)


def make_parser():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                        help="machine-readable JSON output")
    common.add_argument("--no-color", action="store_true", default=argparse.SUPPRESS,
                        help="disable ANSI colors")
    parser = argparse.ArgumentParser(
        prog="urlkit",
        description="URL toolbox: parse, normalize, build and edit URLs. "
                    "Standard library only, no network access.")
    parser.add_argument("--json", action="store_true",
                        help="machine-readable JSON output")
    parser.add_argument("--no-color", action="store_true", help="disable ANSI colors")
    parser.add_argument("--version", action="version", version="urlkit " + __version__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("parse", parents=[common], help="split a URL into components")
    p.add_argument("url")

    p = sub.add_parser("normalize", parents=[common],
                       help="lowercase scheme/host, drop default port, resolve "
                            "dot segments, percent-encode, drop empty fragment")
    p.add_argument("url")

    p = sub.add_parser("build", parents=[common], help="assemble a URL from parts")
    p.add_argument("--scheme", required=True)
    p.add_argument("--host", required=True)
    p.add_argument("--port", type=int, default=None)
    p.add_argument("--path", default="")
    p.add_argument("--query", action="append", default=[], metavar="K=V",
                   help="repeatable query parameter")
    p.add_argument("--fragment", default="")
    p.add_argument("--userinfo", default=None, help="optional user[:password]")

    p = sub.add_parser("query", parents=[common], help="edit the query string")
    p.add_argument("url")
    p.add_argument("--set", action="append", default=[], metavar="K=V",
                   help="replace k in place or append it (repeatable)")
    p.add_argument("--remove", action="append", default=[], metavar="K",
                   help="drop every occurrence of k (repeatable)")
    return parser


def main(argv=None):
    opts = make_parser().parse_args(argv)
    color = color_enabled(opts.no_color)
    try:
        if opts.command == "parse":
            parts = parse_url(opts.url)
            out = json.dumps(parts, indent=2) if opts.json else render_parse(parts, color)
        elif opts.command == "normalize":
            src = opts.url.strip()
            result = normalize_url(opts.url)
            if opts.json:
                out = json.dumps({"input": src, "normalized": result,
                                  "changed": result != src}, indent=2)
            else:
                out = render_url(result, color)
        elif opts.command == "build":
            result = build_url({"scheme": opts.scheme, "userinfo": opts.userinfo,
                                "host": opts.host, "port": opts.port,
                                "path": opts.path,
                                "query": [split_kv(q) for q in opts.query],
                                "fragment": opts.fragment})
            out = json.dumps({"url": result}, indent=2) if opts.json else render_url(result, color)
        else:  # query
            src = opts.url.strip()
            result = modify_query(opts.url, opts.set, opts.remove)
            if opts.json:
                out = json.dumps({"input": src, "url": result,
                                  "query": parse_url(result)["query"],
                                  "changed": result != src}, indent=2)
            else:
                out = render_url(result, color)
    except BadUrl as exc:
        sys.stderr.write("urlkit: %s\n" % exc)
        return 2
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())