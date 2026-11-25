"""Reads TradeSkillMaster.lua (WTF/Account/<account>/SavedVariables) as data with server/luadata.py; nothing is run.

What it takes out:
  ledger      TSM's accounting: r@<realm>@internalData@csv{Sales,Buys,Cancelled,Expired,Expense,Income}, CSV text with
              a header row. Each row becomes a dict keyed by that header.
  characters  s@<Name Realm> - <Faction> - <realm>@internalData@{money,classKey,goldLogLastUpdate}; goldLogLastUpdate
              (unix time) says how new the character's numbers are, so an older file never overwrites newer ones
  inventory   s@...@internalData@{bag,bank,mail,auction,...}Quantity: item -> count, per character
  crafts      f@<Faction> - <realm>@internalData@crafts: the recipes the game told TSM (spell -> mats, numResult)
  vendor      g@ @internalData@vendorItems: item -> vendor buy price (full price; reputation discounts not included)
  postings    c@<Name Realm> - <realm>@internalData@auctionSaleHints: Lokiy's own auction posts, keyed
              "<name>\x01<itemString>\x01<stack size>\x01<buyout each>" -> unix time posted
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
CHAR_KEY = re.compile(r"^s@(?P<name>.+) - (?P<faction>[^-@]+) - (?P<realm>[^@]+)@internalData@"
                      r"(?P<field>money|classKey|goldLogLastUpdate|(?P<place>\w+)Quantity)$")
CRAFTS_KEY = re.compile(r"^f@[^@]+@internalData@crafts$")
VENDOR_KEY = "g@ @internalData@vendorItems"
HINTS_KEY = re.compile(r"^c@(?P<name>.+) - (?P<realm>[^@]+)@internalData@auctionSaleHints$")
CHAR_FIELDS = {"money": "money", "classKey": "class", "goldLogLastUpdate": "updated"}


def item_id(item_string):
    """"i:14046" or "i:14046::::" -> 14046; anything else (pets, names) -> None"""
    m = re.match(r"^i:(\d+)", str(item_string))
    return int(m.group(1)) if m else None


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
    ledger, chars, crafts, vendor, postings = {}, {}, {}, {}, []
    for key, value in db.items():
        m = LEDGER_KEY.match(key)
        if m and m["csv"] in KINDS and isinstance(value, str):
            ledger.setdefault(KINDS[m["csv"]], []).extend((m["realm"], r) for r in rows(value))
            continue
        m = CHAR_KEY.match(key)
        if m:
            c = chars.setdefault((m["name"], m["realm"]), {"name": m["name"], "realm": m["realm"], "faction": m["faction"],
                                                           "inventory": {}})
            if m["place"]:
                if isinstance(value, dict):
                    c["inventory"][m["place"]] = {i: q for k, q in value.items()
                                                  if (i := item_id(k)) and isinstance(q, int) and q > 0}
            else:
                c[CHAR_FIELDS[m["field"]]] = value
            continue
        if CRAFTS_KEY.match(key) and isinstance(value, dict):
            for spell, craft in value.items():
                if isinstance(craft, dict) and isinstance(craft.get("mats"), dict):
                    crafts[str(spell).replace("c:", "")] = craft
            continue
        m = HINTS_KEY.match(key)
        if m and isinstance(value, dict):
            for hint, at in value.items():
                parts = str(hint).split("\x01")
                if len(parts) == 4 and (i := item_id(parts[1])) and parts[2].isdigit() and parts[3].isdigit() \
                        and isinstance(at, int):
                    postings.append({"name": m["name"], "realm": m["realm"], "item": i, "qty": int(parts[2]),
                                     "price": int(parts[3]), "time": at})
            continue
        if key == VENDOR_KEY and isinstance(value, dict):
            vendor = {i: p for k, p in value.items() if (i := item_id(k)) and isinstance(p, int)}
    return {"ledger": ledger, "characters": list(chars.values()), "crafts": crafts, "vendor": vendor,
            "postings": postings}
