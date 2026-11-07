import csv

from app.kyc import gstin

from tests.conftest import DATA


def test_every_registry_gstin_passes_checksum_with_x_pan_char():
    rows = list(csv.DictReader(open(DATA / "mock_gstin_registry.csv", encoding="utf-8")))
    assert len(rows) == 3534
    assert all(r["gstin"][5] == "X" for r in rows)
    assert all(gstin.checksum_ok(r["gstin"]) for r in rows)


def test_tampered_check_digit_fails():
    g = "32TTNXB7384T1ZW"
    assert gstin.checksum_ok(g)
    assert not gstin.checksum_ok(g[:-1] + ("A" if g[-1] != "A" else "B"))
    assert not gstin.checksum_ok("08YKZXS8189L1ZO")


def test_format():
    assert not gstin.format_ok("32TTNXB7384T1Z")
    assert not gstin.format_ok("AB12345678901ZZ")
    assert gstin.udyam_format_ok("UDYAM-MH-00-1234567")
    assert not gstin.udyam_format_ok("UDYAM-MH-0-1234567")
