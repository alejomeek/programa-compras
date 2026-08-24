from api.purchase_orders_issue import _format_order_number


def test_order_number_omits_year_and_keeps_destination() -> None:
    assert _format_order_number("AV19", 4) == "OC-AV19-0004"


def test_order_number_pads_global_serial() -> None:
    assert _format_order_number("CEDI", 125) == "OC-CEDI-0125"
