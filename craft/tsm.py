"""Reads TradeSkillMaster.lua (WTF/Account/<account>/SavedVariables) as data with server/luadata.py; nothing is run.

What it takes out:
  ledger      TSM's accounting: r@<realm>@internalData@csv{Sales,Buys,Cancelled,Expired,Expense,Income}, CSV text with
              a header row. Each row becomes a dict keyed by that header.
  characters  s@<Name Realm> - <Faction> - <realm>@internalData@{money,classKey}
  crafts      f@<Faction> - <realm>@internalData@crafts: the recipes the game told TSM (spell -> mats, numResult)
"""
import csv
import io
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "server"))
from luadata import Parser  # noqa: E402

KINDS = {"csvSales": "sales", "csvBuys": "buys", "csvCancelled": "cancelled", "csvExpired": "expired",
         "csvExpense": "expense", "csvIncome": "income"}
INT_FIELDS = {"stackSize", "quantity", "price", "time", "amount"}
LEDGER_KEY = re.compile(r"^r@(?P<realm>[^@]+)@internalData@(?P<csv>csv\w+)$")
CHAR_KEY = re.compile(r"^s@(?P<name>.+) - (?P<faction>[^-@]+) - (?P<realm>[^@]+)@internalData@(?P<field>money|classKey)$")
CRAFTS_KEY = re.compile(r"^f@[^@]+@internalData@crafts$")


class NotTSM(ValueError):
    pass


def rows(text):
    reader = csv.reader(io.StringIO(text))
    header = next(reader, None)
    if not header:
        return
    for values in reader:
        if len(values) != len(header):
            continue
        row = dict(zip(header, values))
        for k in INT_FIELDS & row.keys():
            try:
                row[k] = int(row[k])
            except ValueError:
                pass
        yield row


def read(text):
    try:
        top = Parser(text).parse_file()
    except (ValueError, IndexError) as e:
        raise NotTSM(f"Couldn't read the file as a SavedVariables file ({e}).")
    db = top.get("TradeSkillMasterDB")
    if not isinstance(db, dict):
        raise NotTSM("This isn't TradeSkillMaster.lua (no TradeSkillMasterDB in it).")
    ledger, chars, crafts = {}, {}, {}
    for key, value in db.items():
        m = LEDGER_KEY.match(key)
        if m and m["csv"] in KINDS and isinstance(value, str):
            ledger.setdefault(KINDS[m["csv"]], []).extend((m["realm"], r) for r in rows(value))
            continue
        m = CHAR_KEY.match(key)
        if m:
            c = chars.setdefault((m["name"], m["realm"]), {"name": m["name"], "realm": m["realm"], "faction": m["faction"]})
            c["money" if m["field"] == "money" else "class"] = value
            continue
        if CRAFTS_KEY.match(key) and isinstance(value, dict):
            for spell, craft in value.items():
                if isinstance(craft, dict) and isinstance(craft.get("mats"), dict):
                    crafts[str(spell).replace("c:", "")] = craft
    return {"ledger": ledger, "characters": list(chars.values()), "crafts": crafts}
