
import pytest
from taskx.utils.schema_registry import SchemaRegistry

class TestNewSchemaLoading:
    """Test loading of Packet 0001 schemas."""

    def test_registry_lists_new_schemas(self):
        """Registry should list the new case bundle schemas."""
        registry = SchemaRegistry()
        available = registry.available
        
        assert "case_bundle" in available
        assert "implementer_report" in available
        assert "supervisor_review" in available

    def test_registry_loads_case_bundle(self):
        """Should load case_bundle schema as dict."""
        registry = SchemaRegistry()
        schema = registry.get_json("case_bundle")
        assert isinstance(schema, dict)
        assert schema["title"] == "Case Bundle Schema"
        assert "bundle_manifest" in schema["required"]

    def test_registry_loads_implementer_report(self):
        """Should load implementer_report schema as dict."""
        registry = SchemaRegistry()
        schema = registry.get_json("implementer_report")
        assert isinstance(schema, dict)
        assert schema["title"] == "Implementer Report Schema"
        assert "status" in schema["properties"]

    def test_registry_loads_supervisor_review(self):
        """Should load supervisor_review schema as dict."""
        registry = SchemaRegistry()
        schema = registry.get_json("supervisor_review")
        assert isinstance(schema, dict)
        assert schema["title"] == "Supervisor Review Schema"
        assert "decision" in schema["required"]
