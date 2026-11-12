<p align="center"><img src="docs/style/hero.png" alt="urlkit — URL toolbox CLI" width="100%"></p>

<p align="center">
  <a href="README.ru.md"><img src="docs/style/pill-ru.png" alt="README RU" height="42"></a>
  <a href="https://github.com/Celine1337/urlkit/releases"><img src="docs/style/pill-release.png" alt="Releases" height="42"></a>
  <a href="https://github.com/Celine1337/urlkit/actions/workflows/ci.yml"><img src="docs/style/pill-ci.png" alt="CI" height="42"></a>
  <a href="LICENSE"><img src="docs/style/pill-license.png" alt="MIT" height="42"></a>
</p>

<img src="docs/style/sec-about-en.png" alt="About" width="100%">

A small URL toolbox on top of `urllib.parse`. URLs arrive messy — mixed-case
hosts, stray `:80`, `/a/./b/../c` paths, unencoded spaces, dead `#` fragments —
and hand-editing query strings breaks them. urlkit splits, cleans, assembles
and edits URLs from the terminal:

- `parse` — every component, query as ordered decoded pairs;
- `normalize` — canonical form without reordering anything;
- `build` — assemble a URL from flags, validated as it is built;
- `query` — set/remove parameters while the rest stay byte-for-byte intact.

Single file, standard library only, Python 3.9+, no network access.

<img src="docs/style/sec-features-en.png" alt="Features" width="100%">

- `parse` reports scheme, userinfo, host, port, path, query pairs and fragment;
  duplicates and blank values are preserved, percent-encoding is decoded.
- `normalize` lowercases scheme and host, drops default ports (`:80` http,
  `:443` https), resolves `.` / `..` segments per RFC 3986, percent-encodes
  spaces and non-ASCII without double-encoding existing escapes, and drops an
  empty fragment. Idempotent; query order is never touched.
- `build` validates scheme, host (IPv6 gets bracketed) and port range, and
  round-trips: `build(parse(x))` preserves the components of representative URLs.
- `query --set k=v` replaces a key in place (first occurrence, later duplicates
  dropped) or appends it; `--remove k` drops every occurrence and wins over
  `--set`. Untouched parameters keep their original raw encoding.
- `--json` for parse / normalize / query (and build), colored ANSI output with
  `--no-color` and `NO_COLOR`, exit code `2` on empty or invalid URLs.

<img src="docs/style/sec-checks-en.png" alt="Modes" width="100%">

| Mode | What it does |
|------|--------------|
| `parse URL` | split into scheme, userinfo, host, port, path, query pairs, fragment |
| `normalize URL` | lowercase scheme/host, drop default port, resolve dot segments, percent-encode where needed, drop empty fragment |
| `build --scheme S --host H` | assemble from `--port`, `--path`, `--query k=v` (repeatable), `--fragment`, optional `--userinfo` |
| `query URL` | `--set k=v` / `--remove k` (repeatable), other params preserved, stable order |

<img src="docs/style/sec-stack-en.png" alt="Tech stack" width="100%">

<img src="docs/style/chips.png" alt="Python 3.9+, urllib.parse, unittest, JSON; GitHub Actions, Pillow" width="100%">

<img src="docs/style/sec-quick-en.png" alt="Quick start" width="100%">

```console
$ python urlkit.py parse "https://user:pass@Example.COM:8443/a/b?q=hello%20world&lang=en#docs"
$ python urlkit.py normalize "HTTP://Example.COM:80/a/./b/../c?greeting=hello world&lang=en#"
$ python urlkit.py build --scheme https --host example.com --port 8443 --path /a --query q=1 --fragment top
$ python urlkit.py query "https://example.com/?a=1&b=2" --set a=9 --remove b
$ python urlkit.py parse "https://example.com" --json
```

```
scheme    https
userinfo  user:pass
host      Example.COM
port      8443
path      /a/b
query     2 pairs
  q = hello world
  lang = en
fragment  docs
```

```
http://example.com/a/c?greeting=hello%20world&lang=en
```

Exit codes: `0` — success, `1` — reserved, `2` — empty or invalid URL (also
argparse usage errors).

Limits, on purpose: this is a syntactic RFC 3986-style toolbox, not a
browser-grade WHATWG parser — no IDNA/punycode conversion, no network checks
(it never resolves or fetches anything). A scheme is required, so
`example.com/x` alone is rejected. `normalize` neither sorts nor deduplicates
query parameters, and `parse` keeps the host's original case.

<img src="docs/style/sec-shots-en.png" alt="Screenshots" width="100%">

![parse report](docs/parse.png)

![normalize result](docs/normalize.png)

<img src="docs/style/sec-tests-en.png" alt="Tests" width="100%">

```console
$ python -m unittest discover -s tests -v
```

52 tests cover parsing, validation, normalization, building, round-trips,
query editing, CLI exit codes and color gating. All images are regenerable
offline:

```console
$ pip install pillow
$ python tools/make_shots.py      # docs/parse.png, docs/normalize.png
$ python tools/make_style.py tools/style.json docs/style
```

<img src="docs/style/stats.png" alt="52 tests, 3 OSes in CI, v1.0.0" width="100%">

[MIT](LICENSE) © Celine1337