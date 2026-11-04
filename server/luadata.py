"""Reads a SavedVariables file as Lua *data*: a tokenizer, nothing is run. From the V+ LootTracker's export_json.py."""
import re

TOKEN_RE = re.compile(r"""
    (?P<ws>\s+)
  | (?P<comment>--[^\n]*)
  | (?P<string>"(?:\\.|[^"\\])*")
  | (?P<number>-?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)
  | (?P<name>[A-Za-z_][A-Za-z0-9_]*)
  | (?P<sym>[{}\[\]=,;])
""", re.VERBOSE)

ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", '"': '"', "'": "'", "\n": "\n"}


def unescape(body):
    out, i = [], 0
    while i < len(body):
        ch = body[i]
        if ch != "\\":
            out.append(ch)
            i += 1
            continue
        nxt = body[i + 1]
        if nxt.isdigit():
            m = re.match(r"\d{1,3}", body[i + 1:])
            out.append(chr(int(m.group())))
            i += 1 + len(m.group())
        else:
            out.append(ESCAPES.get(nxt, nxt))
            i += 2
    return "".join(out)


def tokenize(text):
    pos = 0
    while pos < len(text):
        m = TOKEN_RE.match(text, pos)
        if not m:
            raise ValueError(f"Unexpected character at offset {pos}: {text[pos:pos + 20]!r}")
        pos = m.end()
        kind = m.lastgroup
        if kind in ("ws", "comment"):
            continue
        val = m.group()
        if kind == "string":
            yield ("value", unescape(val[1:-1]))
        elif kind == "number":
            yield ("value", float(val) if any(c in val for c in ".eE") else int(val))
        elif kind == "name" and val in ("true", "false", "nil"):
            yield ("value", {"true": True, "false": False, "nil": None}[val])
        else:
            yield (kind, val)


class Parser:
    def __init__(self, text):
        self.tokens = list(tokenize(text))
        self.i = 0

    def peek(self):
        return self.tokens[self.i] if self.i < len(self.tokens) else (None, None)

    def take(self, expected=None):
        tok = self.peek()
        if expected and tok[1] != expected:
            raise ValueError(f"Expected {expected!r}, got {tok!r}")
        self.i += 1
        return tok

    def parse_file(self):
        result = {}
        while self.peek()[0] is not None:
            _, name = self.take()
            self.take("=")
            result[name] = self.parse_value()
        return result

    def parse_value(self):
        kind, val = self.peek()
        if kind == "value":
            self.take()
            return val
        if val == "{":
            return self.parse_table()
        raise ValueError(f"Unexpected token {val!r}")

    def parse_table(self):
        self.take("{")
        entries, next_index = {}, 1
        while self.peek()[1] != "}":
            kind, val = self.peek()
            if val == "[":
                self.take()
                key = self.parse_value()
                self.take("]")
                self.take("=")
                entries[key] = self.parse_value()
            elif kind == "name" and self.tokens[self.i + 1][1] == "=":
                self.take()
                self.take("=")
                entries[val] = self.parse_value()
            else:
                entries[next_index] = self.parse_value()
                next_index += 1
            if self.peek()[1] in (",", ";"):
                self.take()
        self.take("}")
        keys = list(entries.keys())
        if keys and keys == list(range(1, len(keys) + 1)):
            return [entries[k] for k in keys]
        if not keys:
            return {}
        return {str(k): v for k, v in entries.items()}


def as_list(value):
    """Lua tables come back as lists or dicts depending on their keys."""
    if isinstance(value, dict):
        return list(value.values())
    return value or []
