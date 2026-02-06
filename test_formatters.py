"""Quick smoke tests for the formatters module."""
from csdl_explore.formatters import (
    format_property_flags, sort_properties, group_entity_properties,
    format_flag_check, format_search_result_row,
)
from csdl_explore.parser import Property, EntityType, NavigationProperty
from csdl_explore.explorer import SearchResult


def test_format_flag_check():
    assert format_flag_check(True) == "\u2713"
    assert format_flag_check(False) == ""


def test_format_property_flags():
    prop = Property(name="userId", type="Edm.String", required=True, creatable=True, filterable=False)
    flags = format_property_flags(prop, ["userId"])
    roles = [r for _, r in flags]
    assert "key" in roles
    assert "no_filter" in roles
    # KEY property that is also creatable should NOT get separate "C" flag
    texts = [t for t, _ in flags]
    assert "C" not in texts  # creatable suppressed for keys


def test_sort_properties():
    props = {
        "b": Property(name="b", type="Edm.String"),
        "a": Property(name="a", type="Edm.String"),
        "userId": Property(name="userId", type="Edm.String"),
    }
    sorted_p = sort_properties(props, ["userId"])
    assert sorted_p[0].name == "userId"
    assert sorted_p[1].name == "a"
    assert sorted_p[2].name == "b"


def test_group_entity_properties():
    entity = EntityType(
        name="TestEntity",
        keys=["id"],
        properties={
            "id": Property(name="id", type="Edm.String"),
            "name": Property(name="name", type="Edm.String"),
            "customString1": Property(name="customString1", type="Edm.String"),
            "status": Property(name="status", type="Edm.String"),
        },
        navigation={
            "statusNav": NavigationProperty(name="statusNav", relationship="r", from_role="a", to_role="b", target_entity="PicklistOption"),
        },
    )
    groups = group_entity_properties(entity)
    assert len(groups["keys"]) == 1
    assert groups["keys"][0].name == "id"
    assert len(groups["custom"]) == 1
    assert len(groups["lookups"]) == 1
    assert groups["lookups"][0][0].name == "status"
    assert len(groups["standard"]) == 1
    assert groups["standard"][0].name == "name"


def test_format_search_result_row():
    r = SearchResult(type="entity", entity="EmpJob", match="EmpJob")
    tag, entity, match, details, picklist = format_search_result_row(r)
    assert tag == "ENTITY"
    assert entity == "EmpJob"

    r2 = SearchResult(type="property", entity="EmpJob", match="userId", property="userId", prop_type="Edm.String")
    tag2, _, match2, _, _ = format_search_result_row(r2)
    assert tag2 == "PROP"
    assert match2 == ".userId"


if __name__ == "__main__":
    test_format_flag_check()
    test_sort_properties()
    test_format_property_flags()
    test_group_entity_properties()
    test_format_search_result_row()
    print("All formatter tests passed!")
