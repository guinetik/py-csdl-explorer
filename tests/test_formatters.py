from csdl_explore.formatters import (
    fuzzy_match,
    build_odata_url,
    build_odata_query_params,
    format_property_table_row,
    compute_picklist_impact,
)
from csdl_explore.parser import Property


def test_fuzzy_match_positive():
    assert fuzzy_match("abc", "aXbXcX") is True


def test_fuzzy_match_negative():
    assert fuzzy_match("abc", "aXcXbX") is False


def test_fuzzy_match_empty_pattern():
    assert fuzzy_match("", "anything") is True


def test_build_odata_url_basic():
    url = build_odata_url("https://api.sap.com/odata/v2", "EmpJob", {"$top": "10"})
    assert url == "https://api.sap.com/odata/v2/EmpJob?$top=10&$format=json"


def test_build_odata_url_trailing_slash():
    url = build_odata_url("https://api.sap.com/odata/v2/", "EmpJob", {})
    assert url == "https://api.sap.com/odata/v2/EmpJob?$format=json"


def test_build_odata_url_empty_base():
    url = build_odata_url("", "EmpJob", {"$top": "5"})
    assert "EmpJob" in url


def test_build_odata_query_params():
    params = build_odata_query_params(
        selected=["firstName", "lastName"],
        filter_expr="startDate gt datetime'2024-01-01'",
        orderby_prop="firstName",
        orderby_dir="asc",
        expanded=["personNav"],
        top="20",
    )
    assert params["$select"] == "firstName,lastName"
    assert params["$filter"] == "startDate gt datetime'2024-01-01'"
    assert params["$orderby"] == "firstName asc"
    assert params["$expand"] == "personNav"
    assert params["$top"] == "20"


def test_build_odata_query_params_empty():
    params = build_odata_query_params(
        selected=[], filter_expr="", orderby_prop="",
        orderby_dir="asc", expanded=[], top="20",
    )
    assert "$select" not in params
    assert "$filter" not in params
    assert "$orderby" not in params
    assert "$expand" not in params
    assert params["$top"] == "20"


def _make_prop(name, **kwargs) -> Property:
    defaults = dict(
        type="Edm.String", max_length="", label="", picklist="",
        required=False, creatable=False, updatable=False,
        upsertable=False, visible=True, sortable=False, filterable=False,
    )
    defaults.update(kwargs)
    return Property(name=name, **defaults)


def test_format_property_table_row_key():
    prop = _make_prop("userId", type="Edm.String", required=True)
    row = format_property_table_row(prop, keys=["userId"], accent_color="#ffd700")
    assert "#ffd700" in row[0]
    assert row[5] == "\u2713"


def test_format_property_table_row_nonkey():
    prop = _make_prop("firstName", type="Edm.String", label="First Name")
    row = format_property_table_row(prop, keys=["userId"], accent_color="#ffd700")
    assert row[0] == "firstName"
    assert row[3] == "First Name"


def test_compute_picklist_impact():
    props = {
        "EmpJob": [
            _make_prop("status", required=True, creatable=True),
            _make_prop("category", required=False, creatable=True),
        ],
        "PerPersonal": [
            _make_prop("gender", required=True, creatable=False),
        ],
    }
    impact = compute_picklist_impact(props)
    assert impact["required_count"] == 2
    assert impact["create_entity_count"] == 1
    assert len(impact["required_props"]) == 2
    assert "EmpJob" in impact["create_entities"]


# ── format_odata_value ──────────────────────────────────────────────

from csdl_explore.formatters import format_odata_value


def test_format_odata_value_sap_date():
    assert format_odata_value("/Date(1704067200000)/") == "2024-01-01"


def test_format_odata_value_sap_date_with_offset():
    assert format_odata_value("/Date(1704067200000+0000)/") == "2024-01-01"


def test_format_odata_value_negative_timestamp():
    # Before epoch: 1969-12-31
    assert format_odata_value("/Date(-86400000)/") == "1969-12-31"


def test_format_odata_value_passthrough():
    assert format_odata_value("John Doe") == "John Doe"
    assert format_odata_value("") == ""
    assert format_odata_value("2024-01-01") == "2024-01-01"
