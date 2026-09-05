import pytest
from scanners.onionscan_parser import OnionScanParser, INDICATOR_WEIGHTS
from models.enums import IndicatorType

def test_onionscan_parser_weights_and_types():
    report = {
        "hiddenService": "target.onion",
        "date": "2026-09-05T12:00:00Z",
        "analyticsIDs": ["UA-111111-1"],
        "exifLeaks": ["Camera: TestCam"],
        "serverStatus": "Apache 2.4 /server-status",
        "sshKeys": ["ssh-rsa AAAAB3..."],
        "certificates": ["A1B2C3D4E5F67890123456789ABCDEF0123456789ABCDEF0123456789ABCDEF0"],
        "openDirectories": ["/uploads/"]
    }

    parser = OnionScanParser()
    units = parser.parse_report(report_data=report, target_entity="actor_target")
    assert len(units) == 6

    by_type = {u.indicator_type: u for u in units}

    # Verify exact weights from Dev A Plan
    assert by_type[IndicatorType.onionscan_analytics_id.value].confidence_weight == 0.85
    assert by_type[IndicatorType.onionscan_exif_leak.value].confidence_weight == 0.75
    assert by_type[IndicatorType.onionscan_server_status.value].confidence_weight == 0.65
    assert by_type[IndicatorType.onionscan_ssh_key.value].confidence_weight == 0.60
    assert by_type[IndicatorType.onionscan_certificate.value].confidence_weight == 0.50
    assert by_type[IndicatorType.onionscan_open_directory.value].confidence_weight == 0.40

    # Verify EC-08 limitations present in all
    for u in units:
        assert any("Shared hosting" in lim for lim in u.limitations)
        assert u.category == "I"

def test_onionscan_parser_empty_report():
    parser = OnionScanParser()
    units = parser.parse_report(report_data={}, target_entity="actor_target")
    assert units == []
