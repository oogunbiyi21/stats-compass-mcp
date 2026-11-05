"""Fetch UCI Online Retail II and build the daily series the checker reads.

Online Retail II (Chen, 2012; UCI Machine Learning Repository, CC BY 4.0,
https://doi.org/10.24432/C5CG6D): every line of a UK online gift-ware retailer's
invoices, 1 Dec 2009 to 9 Dec 2011. Most customers are wholesalers.

Daily net sales = sum of Quantity × Price over every invoice line that day,
cancellations ("C" invoices, negative quantities) included, as a store's net
sales report would. Days with no invoices (Saturdays, the Christmas closures)
are 0, as Shopify's "Total sales over time" report shows a day with no sales.

Writes data/uci_all.csv (all countries) and data/uci_uk.csv (United Kingdom),
in the report's columns (Day, Gross sales, Discounts, Net sales; no discounts).

Run: python -I validation/fetch_uci.py
"""

import hashlib
import io
import sys
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

URL = "https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip"
SHA256 = "572e36277c2390fbfde10664750731e0a86f55e33470d91919085f0408e67bfb"  # fetched 5 Nov 2026
DATA = Path(__file__).parent / "data"


def fetch() -> bytes:
    DATA.mkdir(exist_ok=True)
    zipped = DATA / "online_retail_ii.zip"
    if not zipped.exists():
        zipped.write_bytes(urllib.request.urlopen(URL).read())
    body = zipped.read_bytes()
    digest = hashlib.sha256(body).hexdigest()
    if digest != SHA256:
        sys.exit(f"sha256 {digest} isn't the one recorded ({SHA256}): the file changed upstream.")
    return body


def lines(body: bytes) -> pd.DataFrame:
    with zipfile.ZipFile(io.BytesIO(body)) as z:
        sheets = pd.read_excel(z.open("online_retail_II.xlsx"), sheet_name=None, engine="openpyxl")
    df = pd.concat(sheets.values(), ignore_index=True).drop_duplicates()
    df["Day"] = pd.to_datetime(df["InvoiceDate"]).dt.normalize()
    df["Amount"] = df["Quantity"] * df["Price"]
    return df


def report(df: pd.DataFrame) -> pd.DataFrame:
    net = df.groupby("Day")["Amount"].sum()
    days = pd.date_range(net.index.min(), net.index.max(), freq="D")
    net = net.reindex(days, fill_value=0.0).round(2)
    return pd.DataFrame({"Day": days.strftime("%Y-%m-%d"), "Gross sales": net.values, "Discounts": 0.0, "Net sales": net.values})


if __name__ == "__main__":
    df = lines(fetch())
    for name, part in (("all", df), ("uk", df[df["Country"] == "United Kingdom"])):
        out = report(part)
        out.to_csv(DATA / f"uci_{name}.csv", index=False)
        print(f"uci_{name}.csv: {len(out)} days, {out['Day'].iloc[0]} to {out['Day'].iloc[-1]}, "
              f"{int((out['Net sales'] == 0).sum())} zero days, {int((out['Net sales'] < 0).sum())} negative days")
    # Duplicated invoice lines are dropped (the file repeats some exactly).
    df.to_pickle(DATA / "lines.pkl")
