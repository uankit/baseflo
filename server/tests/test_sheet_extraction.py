from __future__ import annotations

import sys
from datetime import datetime
from io import BytesIO
from pathlib import Path

CONNECTORS_ROOT = Path(__file__).resolve().parents[2] / "connectors"
if str(CONNECTORS_ROOT) not in sys.path:
    sys.path.insert(0, str(CONNECTORS_ROOT))


def test_spreadsheet_preprocessor_preserves_raw_grid_rows_and_cells() -> None:
    from connectors.spreadsheet_preprocessor import preprocess_grid, preview_rows

    values = [
        ["", " ", " ", ""],
        ["DATE", "PARTY NAME", "T01", "T02", "", "DATE"],
        ["", "", "", "", "", ""],
        ["2026-04-01", "FARHAN", "10", "", "", "2026-04-01"],
        ["2026-04-02", "SHREE SATI", "", "140", "", "2026-04-02"],
    ]

    tables = preprocess_grid("ADGRBD", values, source="test_grid")

    assert len(tables) == 1
    table = tables[0]
    assert table.name == "adgrbd"
    assert table.source == "test_grid"
    assert table.columns == [
        "row_number",
        "column_1",
        "column_2",
        "column_3",
        "column_4",
        "column_5",
        "column_6",
    ]
    assert table.rows == [
        [1, None, None, None, None, None, None],
        [2, "DATE", "PARTY NAME", "T01", "T02", None, "DATE"],
        [3, None, None, None, None, None, None],
        [4, "2026-04-01", "FARHAN", "10", None, None, "2026-04-01"],
        [5, "2026-04-02", "SHREE SATI", None, "140", None, "2026-04-02"],
    ]
    assert table.metadata["format"] == "canonical_grid_v1"
    assert table.metadata["grid_width"] == 6
    assert table.metadata["grid_height"] == 5
    assert preview_rows(table, limit=1) == [
        {
            "row_number": 1,
            "column_1": None,
            "column_2": None,
            "column_3": None,
            "column_4": None,
            "column_5": None,
            "column_6": None,
        }
    ]


def test_xlsx_preprocessor_converts_each_tab_to_canonical_grid() -> None:
    import connectors.spreadsheet_preprocessor as preprocessor
    from openpyxl import Workbook

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "ADGRBD"
    worksheet.append(["", "", ""])
    worksheet.append(["DATE", "PARTY NAME", "BILL AMT"])
    worksheet.append([datetime(2026, 4, 1, 14, 30), "ANITA", 1200])
    stream = BytesIO()
    workbook.save(stream)

    tables = preprocessor.preprocess_xlsx_bytes(stream.getvalue(), filename="demo.xlsx")

    assert len(tables) == 1
    assert tables[0].name == "adgrbd"
    assert tables[0].source == "openpyxl_canonical_grid"
    assert tables[0].columns == ["row_number", "column_1", "column_2", "column_3"]
    assert tables[0].rows == [
        [1, None, None, None],
        [2, "DATE", "PARTY NAME", "BILL AMT"],
        [3, "2026-04-01T14:30:00", "ANITA", 1200],
    ]


def test_canonical_column_sanitizer_handles_blank_duplicate_and_quotes() -> None:
    from app.data_plane import CANONICAL_META_COLUMNS
    from app.data_plane.naming import (
        canonical_storage_columns,
        quote_ident,
        unique_column_names,
    )
    from app.data_plane.values import duckdb_storage_value

    assert unique_column_names(["", " ", "DATE", "DATE", 'bad"name']) == [
        "column_1",
        "column_2",
        "DATE",
        "DATE_2",
        'bad"name',
    ]
    assert quote_ident('bad"name') == '"bad""name"'

    storage_columns, source_by_storage = canonical_storage_columns(
        ["column_1", "_bf_record_id", "DATE"]
    )
    assert storage_columns[: len(CANONICAL_META_COLUMNS)] == CANONICAL_META_COLUMNS
    assert "source__bf_record_id" in storage_columns
    assert source_by_storage["_bf_record_id"] is None
    assert source_by_storage["source__bf_record_id"] == "_bf_record_id"
    assert source_by_storage["column_1"] == "column_1"
    assert duckdb_storage_value({"nested": [1, "two"]}) == '{"nested": [1, "two"]}'


def test_schema_to_dict_json_encodes_sample_values() -> None:
    from connectors.base import ColumnSchema, SourceSchema, TableSchema
    from connectors.types import DataType

    from app.data_onboarding.service import _schema_to_dict

    payload = _schema_to_dict(
        SourceSchema(
            tables=[
                TableSchema(
                    name="orders",
                    label="Orders",
                    metadata={"preview_rows": [{"row_number": 1}]},
                    columns=[
                        ColumnSchema(
                            name="created_at",
                            data_type=DataType.TEXT,
                            sample_values=[datetime(2026, 5, 14, 9, 15)],
                        )
                    ],
                )
            ]
        )
    )

    assert payload["tables"][0]["columns"][0]["sample_values"] == [
        "2026-05-14T09:15:00"
    ]
    assert payload["tables"][0]["metadata"] == {"preview_rows": [{"row_number": 1}]}


def test_canonical_asset_type_is_source_neutral() -> None:
    from app.data_plane.catalog import asset_type_from_metadata

    assert asset_type_from_metadata({"format": "canonical_grid_v1"}) == "grid"
    assert asset_type_from_metadata({"asset_type": "json_records"}) == "json_records"
    assert asset_type_from_metadata({}) == "records"
