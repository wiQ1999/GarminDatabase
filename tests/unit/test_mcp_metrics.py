from garmin_database.application.mcp_metrics import MCP_PARAMETERS, SOURCE_PARAMETERS
from garmin_database.application.parameter_descriptions import DESCRIPTIONS
from garmin_database.domain.aggregation import MEAN_PARAMETERS


def test_every_mcp_parameter_has_reviewed_explicit_description():
    assert MCP_PARAMETERS == MEAN_PARAMETERS | SOURCE_PARAMETERS
    assert not MEAN_PARAMETERS & SOURCE_PARAMETERS
    assert len(MCP_PARAMETERS) == 43
    assert all(DESCRIPTIONS[key].evidence != "not_documented" for key in MCP_PARAMETERS)
    assert "sleep_disruption_overnight_severity.severity" not in MCP_PARAMETERS
    assert "skin_temp_overnight.nightly_value" not in MCP_PARAMETERS
