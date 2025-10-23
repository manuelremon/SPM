import pandas as pd
from pathlib import Path

class Catalog:
    def __init__(self, csv_path: str = "data/catalogo.csv"):
        p = Path(csv_path)
        if not p.exists():
            self.df = pd.DataFrame(columns=["codigo", "descripcion", "uom", "planta", "equivalentes"])
        else:
            self.df = pd.read_csv(p)
        self.df["desc_norm"] = self.df["descripcion"].str.lower()

    def search(self, texto: str, planta: str | None = None):
        t = (texto or "").lower()
        df = self.df
        if planta and planta.lower() != "todos":
            df = df[(df["planta"].str.lower() == planta.lower()) | (df["planta"].str.lower() == "todos")]
        hits = df[df["desc_norm"].str.contains("|".join([w for w in t.split() if len(w) > 2]), na=False, regex=True)]
        if hits.empty and len(df):
            return df.iloc[0].to_dict(), 0.2
        if hits.empty:
            return None, 0.0
        row = hits.iloc[0].to_dict()
        return row, 0.7

