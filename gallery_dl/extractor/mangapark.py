# -*- coding: utf-8 -*-

# Copyright 2015-2023 Mike Fährmann
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation.

"""Extractors for https://mangapark.net/"""

from .common import ChapterExtractor, MangaExtractor
from .. import text, util, exception
import re


class MangaparkBase():
    """Base class for mangapark extractors"""
    category = "mangapark"
    root_fmt = "https://v2.mangapark.{}"
    browser = "firefox"

    @staticmethod
    def parse_chapter_path(path, data):
        """Get volume/chapter information from url-path of a chapter"""
        data["volume"], data["chapter_minor"] = 0, ""
        for part in path.split("/")[1:]:
            key, value = part[0], part[1:]
            if key == "c":
                chapter, dot, minor = value.partition(".")
                data["chapter"] = text.parse_int(chapter)
                data["chapter_minor"] = dot + minor
            elif key == "i":
                data["chapter_id"] = text.parse_int(value)
            elif key == "v":
                data["volume"] = text.parse_int(value)
            elif key == "s":
                data["stream"] = text.parse_int(value)
            elif key == "e":
                data["chapter_minor"] = "v" + value

    @staticmethod
    def parse_chapter_title(title, data):
        match = re.search(r"(?i)(?:vol(?:ume)?[ .]*(\d+) )?"
                          r"ch(?:apter)?[ .]*(\d+)(\.\w+)?", title)
        if match:
            vol, ch, data["chapter_minor"] = match.groups()
            data["volume"] = text.parse_int(vol)
            data["chapter"] = text.parse_int(ch)


class MangaparkChapterExtractor(MangaparkBase, ChapterExtractor):
    """Extractor for manga-chapters from mangapark.net"""
    pattern = (r"(?:https?://)?(?:www\.|v2\.)?mangapark\.(me|net|com)"
               r"/manga/([^?#]+/i\d+)")
    test = (
        ("https://mangapark.net/manga/gosu/i811653/c055/1", {
            "count": 50,
            "keyword": "db1ed9af4f972756a25dbfa5af69a8f155b043ff",
        }),
        (("https://mangapark.net/manga"
          "/ad-astra-per-aspera-hata-kenjirou/i662051/c001.2/1"), {
            "count": 40,
            "keyword": "2bb3a8f426383ea13f17ff5582f3070d096d30ac",
        }),
        (("https://mangapark.net/manga"
          "/gekkan-shoujo-nozaki-kun/i2067426/v7/c70/1"), {
            "count": 15,
            "keyword": "edc14993c4752cee3a76e09b2f024d40d854bfd1",
        }),
        ("https://mangapark.me/manga/gosu/i811615/c55/1"),
        ("https://mangapark.com/manga/gosu/i811615/c55/1"),
    )

    def __init__(self, match):
        tld, self.path = match.groups()
        self.root = self.root_fmt.format(tld)
        url = "{}/manga/{}?zoom=2".format(self.root, self.path)
        ChapterExtractor.__init__(self, match, url)

    def metadata(self, page):
        data = text.extract_all(page, (
            ("manga_id"  , "var _manga_id = '", "'"),
            ("chapter_id", "var _book_id = '", "'"),
            ("stream"    , "var _stream = '", "'"),
            ("path"      , "var _book_link = '", "'"),
            ("manga"     , "<h2>", "</h2>"),
            ("title"     , "</a>", "<"),
        ), values={"lang": "en", "language": "English"})[0]

        if not data["path"]:
            raise exception.NotFoundError("chapter")

        self.parse_chapter_path(data["path"], data)
        if "chapter" not in data:
            self.parse_chapter_title(data["title"], data)

        data["manga"], _, data["type"] = data["manga"].rpartition(" ")
        data["manga"] = text.unescape(data["manga"])
        data["title"] = data["title"].partition(": ")[2]
        for key in ("manga_id", "chapter_id", "stream"):
            data[key] = text.parse_int(data[key])

        return data

    def images(self, page):
        data = util.json_loads(text.extr(page, "var _load_pages =", ";"))
        return [
            (text.urljoin(self.root, item["u"]), {
                "width": text.parse_int(item["w"]),
                "height": text.parse_int(item["h"]),
            })
            for item in data
        ]


class MangaparkMangaExtractor(MangaparkBase, MangaExtractor):
    """Extractor for manga from mangapark.net"""
    chapterclass = MangaparkChapterExtractor
    pattern = (r"(?:https?://)?(?:www\.|v2\.)?mangapark\.(me|net|com)"
               r"(/manga/[^/?#]+)/?$")
    test = (
        ("https://mangapark.net/manga/aria", {
            "url": "51c6d82aed5c3c78e0d3f980b09a998e6a2a83ee",
            "keyword": "cabc60cf2efa82749d27ac92c495945961e4b73c",
        }),
        ("https://mangapark.me/manga/aria"),
        ("https://mangapark.com/manga/aria"),
    )

    def __init__(self, match):
        self.root = self.root_fmt.format(match.group(1))
        MangaExtractor.__init__(self, match, self.root + match.group(2))

    def chapters(self, page):
        results = []
        data = {"lang": "en", "language": "English"}
        data["manga"] = text.unescape(
            text.extr(page, '<title>', ' Manga - '))

        for stream in page.split('<div id="stream_')[1:]:
            data["stream"] = text.parse_int(text.extr(stream, '', '"'))

            for chapter in text.extract_iter(stream, '<li ', '</li>'):
                path  , pos = text.extract(chapter, 'href="', '"')
                title1, pos = text.extract(chapter, '>', '<', pos)
                title2, pos = text.extract(chapter, '>: </span>', '<', pos)
                count , pos = text.extract(chapter, '  of ', ' ', pos)

                self.parse_chapter_path(path[8:], data)
                if "chapter" not in data:
                    self.parse_chapter_title(title1, data)

                if title2:
                    data["title"] = title2.strip()
                else:
                    data["title"] = title1.partition(":")[2].strip()

                data["count"] = text.parse_int(count)
                results.append((self.root + path, data.copy()))
                data.pop("chapter", None)

        return results
