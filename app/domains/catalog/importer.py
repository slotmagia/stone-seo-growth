"""Operator-supplied CSV intake. Atomic and evidence-neutral by design."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from dataclasses import dataclass

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Product
from app.schemas import ProductCreate

MAX_CSV_BYTES = 1024 * 1024
MAX_CSV_ROWS = 1000
CORE = ("sku", "title_zh", "title_en", "stone_type")
REQUIRED = {"sku", "title_zh", "stone_type"}
PROPERTY_COLUMN = re.compile(r"^property\.([a-z][a-z0-9_]{0,63})$")


@dataclass
class PreparedImport:
    report: dict
    products: list[ProductCreate]


def _reject(message: str) -> PreparedImport:
    return PreparedImport({
        "source": "operator_uploaded_csv", "rows_received": 0,
        "valid_rows": 0, "would_import": 0, "imported": 0,
        "errors": [{"row": 1, "code": "invalid_file", "message": message}],
    }, [])


def prepare_csv_import(content: bytes, db: Session) -> PreparedImport:
    """Validate entire file, including existing SKU collisions, before any insert.

    Does not trust or verify a product fact; later verification is mandatory.
    A failed file is never partially imported.
    """
    if len(content) > MAX_CSV_BYTES:
        return _reject(f"CSV exceeds {MAX_CSV_BYTES} bytes")
    try:
        decoded = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return _reject("CSV must be UTF-8 (UTF-8 BOM is accepted)")
    if "\x00" in decoded:
        return _reject("CSV contains NUL bytes")
    sha = hashlib.sha256(content).hexdigest()
    try:
        reader = csv.DictReader(io.StringIO(decoded, newline=""), strict=True)
        headers = reader.fieldnames
        if not headers:
            return _reject("CSV requires a header row")
        headers = [h.strip() for h in headers]
        if len(headers) != len(set(headers)):
            return _reject("CSV contains duplicate column names")
        if len(headers) > 24:
            return _reject("CSV exceeds 24 columns")
        unexpected = [h for h in headers if h not in CORE and not PROPERTY_COLUMN.fullmatch(h)]
        missing = sorted(REQUIRED - set(headers))
        if unexpected or missing:
            return _reject(f"Missing columns: {missing}; unsupported columns: {unexpected}")
        reader.fieldnames = headers
        raw_rows = list(reader)
    except (csv.Error, ValueError) as exc:
        return _reject(f"Malformed CSV: {type(exc).__name__}")
    if len(raw_rows) > MAX_CSV_ROWS:
        return _reject(f"CSV exceeds {MAX_CSV_ROWS} data rows")

    errors: list[dict] = []
    parsed: list[tuple[int, ProductCreate]] = []
    file_skus: set[str] = set()
    for number, raw in enumerate(raw_rows, start=2):
        if None in raw or any(value is None for value in raw.values()):
            errors.append({"row": number, "code": "column_count", "message": "Incorrect column count"})
            continue
        values = {key: value.strip() for key, value in raw.items()}
        if not any(values.values()):
            continue
        sku = values.get("sku", "").upper()
        if not sku or not values.get("title_zh") or not values.get("stone_type"):
            errors.append({"row": number, "code": "required", "message": "sku, title_zh and stone_type are required"})
            continue
        if sku.casefold() in file_skus:
            errors.append({"row": number, "code": "duplicate_in_file", "message": f"Duplicate SKU: {sku}"})
            continue
        file_skus.add(sku.casefold())
        properties = {}
        bad_property = False
        for column, value in values.items():
            match = PROPERTY_COLUMN.fullmatch(column)
            if not match or not value:
                continue
            if len(value) > 500:
                errors.append({"row": number, "code": "property_size", "message": f"Property too long: {column}"})
                bad_property = True
                break
            if value.startswith(("[", "{")):
                try:
                    parsed_value = json.loads(value)
                except json.JSONDecodeError:
                    errors.append({"row": number, "code": "property_json", "message": f"Malformed JSON property: {column}"})
                    bad_property = True
                    break
                if not isinstance(parsed_value, (dict, list)):
                    errors.append({"row": number, "code": "property_json", "message": f"Expected JSON object/array: {column}"})
                    bad_property = True
                    break
                properties[match.group(1)] = parsed_value
            else:
                properties[match.group(1)] = value
        if bad_property:
            continue
        try:
            validated = ProductCreate.model_validate({
                "sku": sku, "title_zh": values["title_zh"],
                "title_en": values.get("title_en") or None,
                "stone_type": values["stone_type"], "properties": properties,
            })
        except ValidationError as exc:
            errors.append({"row": number, "code": "field_validation", "message": "; ".join(
                f"{'.'.join(str(s) for s in e['loc'])}: {e['msg']}" for e in exc.errors()
            )[:400]})
            continue
        parsed.append((number, validated))

    if parsed:
        incoming = [item.sku.lower() for _, item in parsed]
        existing = set(db.scalars(select(func.lower(Product.sku)).where(
            func.lower(Product.sku).in_(incoming)
        )).all())
        for number, item in parsed:
            if item.sku.lower() in existing:
                errors.append({"row": number, "code": "already_exists", "message": f"SKU already exists: {item.sku}"})
    errors.sort(key=lambda issue: issue["row"])
    valid = len(parsed) - sum(e["code"] == "already_exists" for e in errors)
    report = {
        "source": "operator_uploaded_csv", "sha256": sha,
        "rows_received": len(raw_rows), "valid_rows": valid,
        "would_import": valid if not errors else 0,
        "imported": 0, "errors": errors,
        "note": "Atomic batch: any error prevents all inserts. Imported facts remain unverified.",
    }
    return PreparedImport(report, [item for _, item in parsed] if not errors else [])
