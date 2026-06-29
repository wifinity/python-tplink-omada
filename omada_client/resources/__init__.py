"""Resource exports."""

from .aps import APsResource
from .ap_groups import APGroupsResource
from .devices import DevicesResource
from .olts import OLTsResource
from .radius_profiles import RadiusProfilesResource
from .sites import SitesResource
from .switches import SwitchesResource
from .wifi_networks import WiFiNetworksResource
from .wlan_groups import WLANGroupsResource

__all__ = [
    "SitesResource",
    "DevicesResource",
    "RadiusProfilesResource",
    "WiFiNetworksResource",
    "WLANGroupsResource",
    "APGroupsResource",
    "APsResource",
    "OLTsResource",
    "SwitchesResource",
]
