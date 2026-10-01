"""Resource exports."""

from .aps import APsResource
from .ap_groups import APGroupsResource
from .devices import DevicesResource
from .dhcp_snooping import DhcpSnoopingResource
from .lan_networks import LanNetworksResource
from .olts import OLTsResource
from .radius_profiles import RadiusProfilesResource
from .site_services import SiteServicesResource
from .site_wireless import SiteWirelessResource
from .sites import SitesResource
from .switch_dot1x import SwitchDot1xResource
from .switches import SwitchesResource
from .wifi_networks import WiFiNetworksResource

__all__ = [
    "SitesResource",
    "SiteServicesResource",
    "SiteWirelessResource",
    "DevicesResource",
    "DhcpSnoopingResource",
    "LanNetworksResource",
    "RadiusProfilesResource",
    "WiFiNetworksResource",
    "APGroupsResource",
    "APsResource",
    "OLTsResource",
    "SwitchesResource",
    "SwitchDot1xResource",
]
