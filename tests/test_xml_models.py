"""Test XML config models."""
import sys
sys.path.insert(0, "D:\\Personal_Projects\\DayzModManager")

from src.models.xml_config_models import (
    ConfigTypeRegistry, XMLMergeHelper, 
    TypesXMLModel, SpawnableTypesXMLModel, RandomPresetsXMLModel,
    EventsXMLModel, EventSpawnsXMLModel, IgnoreListXMLModel,
    WeatherXMLModel, EconomyCoreXMLModel, EnvironmentXMLModel,
    MapGroupXMLModel, MapProtoXMLModel,
    MergeStrategy, FieldMergeRule
)


def test_filename_detection():
    """Test filename pattern detection."""
    test_cases = [
        ("types.xml", TypesXMLModel),
        ("Types.xml", TypesXMLModel),
        ("bandit_types.xml", TypesXMLModel),
        ("custom_types.xml", TypesXMLModel),
        ("cfgspawnabletypes.xml", SpawnableTypesXMLModel),
        ("cfgrandompresets.xml", RandomPresetsXMLModel),
        ("events.xml", EventsXMLModel),
        ("cfgeventspawns.xml", EventSpawnsXMLModel),
        ("cfgignorelist.xml", IgnoreListXMLModel),
        ("cfgweather.xml", WeatherXMLModel),
        ("cfgeconomycore.xml", EconomyCoreXMLModel),
        ("cfgenvironment.xml", EnvironmentXMLModel),
        ("mapgroupcluster.xml", MapGroupXMLModel),
        ("mapgroupcluster01.xml", MapGroupXMLModel),
        ("mapgroupcluster05.xml", MapGroupXMLModel),
        ("mapgrouppos.xml", MapGroupXMLModel),
        ("mapgroupdirt.xml", MapGroupXMLModel),
        ("mapgroupproto.xml", MapProtoXMLModel),
        ("mapclusterproto.xml", MapProtoXMLModel),
    ]
    
    print("=" * 60)
    print("FILENAME DETECTION TEST")
    print("=" * 60)
    
    for filename, expected_model in test_cases:
        result = ConfigTypeRegistry.get_model_by_filename(filename)
        status = "✓" if result == expected_model else "✗"
        result_name = result.__name__ if result else "None"
        expected_name = expected_model.__name__
        print(f"{status} {filename:30} -> {result_name:25} (expected: {expected_name})")


def test_root_element_detection():
    """Test root element detection."""
    test_cases = [
        ("types", TypesXMLModel),
        ("spawnabletypes", SpawnableTypesXMLModel),
        ("randompresets", RandomPresetsXMLModel),
        ("events", EventsXMLModel),
        ("eventposdef", EventSpawnsXMLModel),
        ("ignore", IgnoreListXMLModel),
        ("weather", WeatherXMLModel),
        ("economycore", EconomyCoreXMLModel),
        ("env", EnvironmentXMLModel),
        ("map", MapGroupXMLModel),
        ("prototype", MapProtoXMLModel),
    ]
    
    print("\n" + "=" * 60)
    print("ROOT ELEMENT DETECTION TEST")
    print("=" * 60)
    
    for root_element, expected_model in test_cases:
        result = ConfigTypeRegistry.get_model_by_root_element(root_element)
        status = "✓" if result == expected_model else "✗"
        result_name = result.__name__ if result else "None"
        expected_name = expected_model.__name__
        print(f"{status} <{root_element:20}> -> {result_name:25} (expected: {expected_name})")


def test_merge_rules():
    """Test merge rules for different models."""
    print("\n" + "=" * 60)
    print("MERGE RULES TEST")
    print("=" * 60)
    
    # TypesXMLModel
    print("\nTypesXMLModel:")
    mergeable = XMLMergeHelper.get_mergeable_fields(TypesXMLModel)
    unique = XMLMergeHelper.get_unique_fields(TypesXMLModel)
    print(f"  Mergeable fields: {mergeable}")
    print(f"  Unique fields: {unique}")
    print(f"  Merge strategy: {TypesXMLModel.get_merge_strategy()}")
    
    # SpawnableTypesXMLModel
    print("\nSpawnableTypesXMLModel:")
    mergeable = XMLMergeHelper.get_mergeable_fields(SpawnableTypesXMLModel)
    unique = XMLMergeHelper.get_unique_fields(SpawnableTypesXMLModel)
    print(f"  Mergeable fields: {mergeable}")
    print(f"  Unique fields: {unique}")
    print(f"  Merge strategy: {SpawnableTypesXMLModel.get_merge_strategy()}")
    
    # EventsXMLModel
    print("\nEventsXMLModel:")
    mergeable = XMLMergeHelper.get_mergeable_fields(EventsXMLModel)
    unique = XMLMergeHelper.get_unique_fields(EventsXMLModel)
    print(f"  Mergeable fields: {mergeable}")
    print(f"  Unique fields: {unique}")
    print(f"  Merge strategy: {EventsXMLModel.get_merge_strategy()}")


def test_element_signatures():
    """Test element signature generation."""
    from xml.etree import ElementTree as ET
    
    print("\n" + "=" * 60)
    print("ELEMENT SIGNATURE TEST")
    print("=" * 60)
    
    # Test type element with name
    elem1 = ET.fromstring('<type name="M4A1" />')
    sig1 = XMLMergeHelper.get_element_signature(elem1)
    print(f"<type name='M4A1'/> -> {sig1}")
    
    # Test category element
    elem2 = ET.fromstring('<category name="weapons" />')
    sig2 = XMLMergeHelper.get_element_signature(elem2)
    print(f"<category name='weapons'/> -> {sig2}")
    
    # Test pos element
    elem3 = ET.fromstring('<pos x="1234.5" y="100" z="5678.9" a="90" />')
    sig3 = XMLMergeHelper.get_element_signature(elem3)
    print(f"<pos x='1234.5' y='100' z='5678.9' a='90'/> -> {sig3}")
    
    # Test group element
    elem4 = ET.fromstring('<group name="Building1" pos="1 2 3" />')
    sig4 = XMLMergeHelper.get_element_signature(elem4)
    print(f"<group name='Building1' pos='1 2 3'/> -> {sig4}")


if __name__ == "__main__":
    test_filename_detection()
    test_root_element_detection()
    test_merge_rules()
    test_element_signatures()
    print("\n" + "=" * 60)
    print("ALL TESTS COMPLETED")
    print("=" * 60)
