"""
Tabular Loaders — CSV, Excel.
"""
from app.services.providers.loaders.tabular.csv_loader import load as load_csv
from app.services.providers.loaders.tabular.excel_loader import load as load_excel

__all__ = ["load_csv", "load_excel"]
