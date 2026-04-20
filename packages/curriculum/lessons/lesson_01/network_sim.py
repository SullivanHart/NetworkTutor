import ipaddress
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Route:
    network: str
    gateway: Optional[str]
    interface: str
    metric: int
    proto: str  # 'connected', 'static', 'ospf', etc.

    def __post_init__(self):
        self._network_obj = ipaddress.ip_network(self.network, strict=False)

    @property
    def prefix_len(self) -> int:
        return self._network_obj.prefixlen

    def matches(self, dest_ip: str) -> bool:
        try:
            addr = ipaddress.ip_address(dest_ip)
            return addr in self._network_obj
        except ValueError:
            return False

    def __repr__(self):
        gw = self.gateway or "directly connected"
        return (
            f"Route({self.network} via {gw} dev {self.interface} "
            f"proto={self.proto} metric={self.metric})"
        )


@dataclass
class Interface:
    name: str
    cidr: str
    peer: Optional[str] = None

    def __post_init__(self):
        iface = ipaddress.ip_interface(self.cidr)
        self._ip = iface.ip
        self._network = iface.network

    @property
    def ip(self) -> str:
        return str(self._ip)

    @property
    def network(self) -> str:
        return str(self._network)

    @property
    def prefix_len(self) -> int:
        return self._network.prefixlen


@dataclass
class NetworkDevice:
    name: str
    device_type: str  # 'router', 'host'
    interfaces: list[Interface] = field(default_factory=list)
    routes: list[Route] = field(default_factory=list)

    def lookup_route(self, dest_ip: str) -> Optional[Route]:
        """
        Longest Prefix Match (LPM) - RFC 1812 Section 5.2.4.3.
        Find all routes whose network contains dest_ip, then return
        the one with the longest (most specific) prefix length.
        In case of tie, the one with the lowest metric wins.
        """
        matching: list[Route] = [r for r in self.routes if r.matches(dest_ip)]
        if not matching:
            return None
        # Sort by prefix length descending, then metric ascending
        matching.sort(key=lambda r: (-r.prefix_len, r.metric))
        return matching[0]

    def get_all_matching_routes(self, dest_ip: str) -> list[Route]:
        """Return all matching routes sorted by LPM (best first)."""
        matching = [r for r in self.routes if r.matches(dest_ip)]
        matching.sort(key=lambda r: (-r.prefix_len, r.metric))
        return matching

    def add_route(
        self,
        network: str,
        gateway: Optional[str],
        interface: str,
        metric: int = 1,
        proto: str = "static",
    ) -> bool:
        """Add a route. Returns False if an identical network already exists."""
        norm = str(ipaddress.ip_network(network, strict=False))
        for r in self.routes:
            if str(ipaddress.ip_network(r.network, strict=False)) == norm:
                # Replace the existing route
                self.routes.remove(r)
                break
        self.routes.append(Route(norm, gateway, interface, metric, proto))
        return True

    def del_route(self, network: str) -> bool:
        """Delete a route by network prefix. Returns True if found and removed."""
        norm = str(ipaddress.ip_network(network, strict=False))
        for r in self.routes:
            if str(ipaddress.ip_network(r.network, strict=False)) == norm:
                self.routes.remove(r)
                return True
        return False

    def get_interface_for_gateway(self, gateway_ip: str) -> Optional[Interface]:
        """Find which local interface can reach a given gateway IP directly."""
        try:
            gw = ipaddress.ip_address(gateway_ip)
        except ValueError:
            return None
        for iface in self.interfaces:
            net = ipaddress.ip_network(iface.cidr, strict=False)
            if gw in net:
                return iface
        return None

    def get_interface_by_name(self, name: str) -> Optional[Interface]:
        for iface in self.interfaces:
            if iface.name == name:
                return iface
        return None


@dataclass
class HopResult:
    device: str
    ip: str
    success: bool
    note: str


class NetworkTopology:
    def __init__(self):
        self.devices: dict[str, NetworkDevice] = {}
        # links: list of (device_a_name, iface_a, device_b_name, iface_b)
        self.links: list[tuple[str, str, str, str]] = []

    def add_device(self, device: NetworkDevice):
        self.devices[device.name] = device

    def add_link(self, dev_a: str, iface_a: str, dev_b: str, iface_b: str):
        self.links.append((dev_a, iface_a, dev_b, iface_b))

    def get_device_for_ip(self, ip: str) -> Optional[NetworkDevice]:
        """Find which device owns a given IP address."""
        for device in self.devices.values():
            for iface in device.interfaces:
                if iface.ip == ip:
                    return device
        return None

    def get_device_owning_network(self, network: str) -> Optional[NetworkDevice]:
        """Find which device has the given network directly connected."""
        try:
            target_net = ipaddress.ip_network(network, strict=False)
        except ValueError:
            return None
        for device in self.devices.values():
            for iface in device.interfaces:
                iface_net = ipaddress.ip_network(iface.cidr, strict=False)
                if iface_net == target_net:
                    return device
        return None

    def simulate_ping(self, src_name: str, dest_ip: str) -> list[HopResult]:
        """
        Walk through the topology hop-by-hop using routing tables.
        Returns a list of HopResult objects describing each hop.
        Stops when:
          - Destination is reached (a device owns dest_ip)
          - No route found at current device
          - A loop is detected (visited device+ip pair seen twice)
        """
        hops: list[HopResult] = []
        visited: set[str] = set()
        MAX_HOPS = 30

        current_device = self.devices.get(src_name)
        if current_device is None:
            return [HopResult(src_name, "?", False, f"Source device '{src_name}' not found")]

        # Determine source IP (first interface)
        if not current_device.interfaces:
            return [HopResult(src_name, "?", False, "Source device has no interfaces")]
        src_ip = current_device.interfaces[0].ip

        try:
            dest_addr = ipaddress.ip_address(dest_ip)
        except ValueError:
            return [HopResult(src_name, src_ip, False, f"Invalid destination IP: {dest_ip}")]

        hop_count = 0
        while hop_count < MAX_HOPS:
            hop_count += 1

            # Check if this device already owns the destination IP
            for iface in current_device.interfaces:
                if iface.ip == dest_ip:
                    hops.append(HopResult(
                        current_device.name,
                        iface.ip,
                        True,
                        "destination reached!",
                    ))
                    return hops

            # Loop detection
            visit_key = f"{current_device.name}:{dest_ip}"
            if visit_key in visited:
                hops.append(HopResult(
                    current_device.name,
                    src_ip,
                    False,
                    "ROUTING LOOP DETECTED - packet discarded",
                ))
                return hops
            visited.add(visit_key)

            # Look up the route
            route = current_device.lookup_route(dest_ip)
            if route is None:
                hops.append(HopResult(
                    current_device.name,
                    src_ip,
                    False,
                    f"NO ROUTE TO {dest_ip} - packet dropped",
                ))
                return hops

            # Determine next hop
            if route.gateway is None or route.proto == "connected":
                # Directly connected - check if destination is on this segment
                iface = current_device.get_interface_by_name(route.interface)
                iface_ip = iface.ip if iface else src_ip
                hops.append(HopResult(
                    current_device.name,
                    iface_ip,
                    True,
                    f"directly connected, delivering via {route.interface}",
                ))
                # Find the destination device
                dest_device = self.get_device_for_ip(dest_ip)
                if dest_device is None:
                    # Destination host not modeled - treat as success (it's on the segment)
                    hops.append(HopResult(
                        "Host",
                        dest_ip,
                        True,
                        "destination reached!",
                    ))
                    return hops
                # Move to destination device
                current_device = dest_device
                src_ip = dest_ip
                continue

            # Gateway-based route
            gateway_ip = route.gateway
            iface = current_device.get_interface_by_name(route.interface)
            iface_ip = iface.ip if iface else src_ip
            hops.append(HopResult(
                current_device.name,
                iface_ip,
                True,
                f"forwarding to {gateway_ip} via {route.interface}",
            ))

            # Find next hop device
            next_device = self.get_device_for_ip(gateway_ip)
            if next_device is None:
                hops.append(HopResult(
                    "?",
                    gateway_ip,
                    False,
                    f"next-hop {gateway_ip} is unreachable (device not in topology)",
                ))
                return hops

            current_device = next_device
            src_ip = gateway_ip

        hops.append(HopResult("?", dest_ip, False, f"TTL exceeded after {MAX_HOPS} hops"))
        return hops
