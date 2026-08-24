from io import BytesIO
from zipfile import ZipFile

from api.purchase_orders_zip import _validate_order_ids, _zip_pdfs


def test_zip_keeps_each_pdf_inside_orders_folder() -> None:
    content = _zip_pdfs([("OC-AV19-0004", b"pdf one"), ("OC-CEDI-0005", b"pdf two")])

    with ZipFile(BytesIO(content)) as archive:
        assert archive.namelist() == ["ordenes-de-compra/OC-AV19-0004.pdf", "ordenes-de-compra/OC-CEDI-0005.pdf"]
        assert archive.read("ordenes-de-compra/OC-CEDI-0005.pdf") == b"pdf two"


def test_zip_selection_rejects_repeated_or_more_than_fifty_orders() -> None:
    repeated, repeated_error = _validate_order_ids(
        {"orderIds": ["00000000-0000-0000-0000-000000000001", "00000000-0000-0000-0000-000000000001"]},
    )
    too_many, too_many_error = _validate_order_ids(
        {"orderIds": [f"00000000-0000-0000-0000-{index:012d}" for index in range(1, 52)]},
    )

    assert repeated is None and repeated_error == "La selección de órdenes no es válida."
    assert too_many is None and too_many_error == "Selecciona entre 1 y 50 órdenes emitidas."
