<p align="center"><img src="docs/style/hero.png" alt="urlkit — CLI-набор инструментов для URL" width="100%"></p>

<p align="center">
  <a href="README.md"><img src="docs/style/pill-en.png" alt="README EN" height="42"></a>
  <a href="https://github.com/Celine1337/urlkit/releases"><img src="docs/style/pill-release.png" alt="Releases" height="42"></a>
  <a href="https://github.com/Celine1337/urlkit/actions/workflows/ci.yml"><img src="docs/style/pill-ci.png" alt="CI" height="42"></a>
  <a href="LICENSE"><img src="docs/style/pill-license.png" alt="MIT" height="42"></a>
</p>

<img src="docs/style/sec-about-ru.png" alt="О проекте" width="100%">

Небольшой набор инструментов для URL поверх `urllib.parse`. URL приходят
грязными — хост в разном регистре, лишние `:80`, пути `/a/./b/../c`,
незакодированные пробелы, мёртвые фрагменты `#` — а ручная правка query-строк
их ломает. urlkit разбирает, чистит, собирает и правит URL из терминала:

- `parse` — все компоненты, query как упорядоченные декодированные пары;
- `normalize` — канонический вид без переупорядочивания;
- `build` — сборка URL из флагов с проверкой на лету;
- `query` — set/remove параметров, остальные остаются байт-в-байт.

Один файл, только стандартная библиотека, Python 3.9+, без сети.

<img src="docs/style/sec-features-ru.png" alt="Возможности" width="100%">

- `parse` показывает scheme, userinfo, host, port, path, пары query и fragment;
  дубликаты и пустые значения сохраняются, percent-encoding декодируется.
- `normalize` приводит scheme и host к нижнему регистру, убирает порты по
  умолчанию (`:80` http, `:443` https), раскрывает сегменты `.` / `..` по
  RFC 3986, кодирует пробелы и не-ASCII без двойного кодирования существующих
  escape-последовательностей и убирает пустой фрагмент. Идемпотентен; порядок
  query не трогается никогда.
- `build` проверяет scheme, host (IPv6 берётся в скобки) и диапазон порта и
  замкнут в круг: `build(parse(x))` сохраняет компоненты репрезентативных URL.
- `query --set k=v` заменяет ключ на месте (первое вхождение, поздние дубликаты
  убираются) или добавляет его; `--remove k` убирает все вхождения и побеждает
  `--set`. Нетронутые параметры сохраняют исходное кодирование.
- `--json` для parse / normalize / query (и build), цветной ANSI-вывод с
  `--no-color` и `NO_COLOR`, код возврата `2` на пустых или невалидных URL.

<img src="docs/style/sec-checks-ru.png" alt="Режимы" width="100%">

| Режим | Что делает |
|-------|------------|
| `parse URL` | разбирает на scheme, userinfo, host, port, path, пары query, fragment |
| `normalize URL` | нижний регистр scheme/host, убирает порт по умолчанию, раскрывает dot-сегменты, кодирует где нужно, убирает пустой фрагмент |
| `build --scheme S --host H` | собирает из `--port`, `--path`, `--query k=v` (повторяемый), `--fragment`, опциональный `--userinfo` |
| `query URL` | `--set k=v` / `--remove k` (повторяемые), остальные параметры сохраняются, порядок стабилен |

<img src="docs/style/sec-stack-ru.png" alt="Технологии" width="100%">

<img src="docs/style/chips.png" alt="Python 3.9+, urllib.parse, unittest, JSON; GitHub Actions, Pillow" width="100%">

<img src="docs/style/sec-quick-ru.png" alt="Быстрый старт" width="100%">

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

Коды возврата: `0` — успех, `1` — зарезервирован, `2` — пустой или невалидный
URL (а также ошибки разбора аргументов).

Ограничения сознательные: это синтаксический набор в духе RFC 3986, а не
браузерный WHATWG-парсер — без IDNA/punycode и без сетевых проверок (ничего не
резолвит и не качает). Scheme обязателен, поэтому `example.com/x` сам по себе
отклоняется. `normalize` не сортирует и не дедуплицирует параметры query, а
`parse` сохраняет исходный регистр хоста.

<img src="docs/style/sec-shots-ru.png" alt="Скриншоты" width="100%">

![отчёт parse](docs/parse.png)

![результат normalize](docs/normalize.png)

<img src="docs/style/sec-tests-ru.png" alt="Тесты" width="100%">

```console
$ python -m unittest discover -s tests -v
```

52 теста покрывают разбор, валидацию, нормализацию, сборку, round-trip,
правку query, коды возврата CLI и управление цветом. Все картинки
перегенерируются офлайн:

```console
$ pip install pillow
$ python tools/make_shots.py      # docs/parse.png, docs/normalize.png
$ python tools/make_style.py tools/style.json docs/style
```

<img src="docs/style/stats.png" alt="52 теста, 3 ОС в CI, v1.0.0" width="100%">

[MIT](LICENSE) © Celine1337