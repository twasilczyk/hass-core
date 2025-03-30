"""Constants for the Disable Components integration."""
from typing import Final

DOMAIN: Final = "disable_components"
DEFAULT_COMPONENTS_TO_DISABLE = ["cloud"]

# Mock implementations for components with special requirements
CLOUD_DATA_KEY = "cloud"
OAUTH_IMPL_KEY = "oauth2_implementations"
ACCOUNT_LINK_KEY = "account_link_impl_funcs"