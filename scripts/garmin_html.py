"""Parse saved HTML as inert data, without database or MCP dependencies."""

from html.parser import HTMLParser
from zoneinfo import ZoneInfo

MONTHS = {
    name: index
    for index, name in enumerate(
        (
            "Jan",
            "Feb",
            "Mar",
            "Apr",
            "May",
            "Jun",
            "Jul",
            "Aug",
            "Sep",
            "Oct",
            "Nov",
            "Dec",
        ),
        1,
    )
}


ZONE = ZoneInfo("Europe/Warsaw")


PHASES = {"Czuwanie": 1, "Przebudzenie": 1, "Płytki": 2, "Głęboki": 3, "REM": 4}


class Node:
    def __init__(self, tag="root", attrs=(), parent=None):
        self.tag, self.attrs, self.parent = tag, dict(attrs), parent
        self.children = []

    def walk(self):
        yield self
        for child in self.children:
            if isinstance(child, Node):
                yield from child.walk()

    def text(self):
        value = " ".join(
            child.text() if isinstance(child, Node) else child
            for child in self.children
        ).strip()
        return " ".join(value.split())

    def has_class(self, prefix):
        return any(c.startswith(prefix) for c in self.attrs.get("class", "").split())


class SavedPage(HTMLParser):
    def __init__(self):
        super().__init__()
        self.root = self.current = Node()

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs, self.current)
        self.current.children.append(node)
        if tag not in {
            "area",
            "base",
            "br",
            "col",
            "embed",
            "hr",
            "img",
            "input",
            "link",
            "meta",
            "param",
            "source",
            "track",
            "wbr",
        }:
            self.current = node

    def handle_startendtag(self, tag, attrs):
        self.current.children.append(Node(tag, attrs, self.current))

    def handle_endtag(self, tag):
        node = self.current
        while node.parent is not None:
            if node.tag == tag:
                self.current = node.parent
                return
            node = node.parent

    def handle_data(self, data):
        self.current.children.append(data)

    def cards(self):
        for label in self.root.walk():
            if label.has_class("SleepScoreSummary_dailySleepScoreValue"):
                yield "Ocena jakości snu", label.text()
            if not label.has_class("DataBlock_dataLabel"):
                continue
            parent = label.parent
            fields = [n for n in parent.walk() if n.has_class("DataBlock_dataField")]
            if len(fields) == 1:
                yield label.text(), fields[0].text()
