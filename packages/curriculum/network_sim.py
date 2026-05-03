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
            return ipaddress.ip_address(dest_ip) in self._network_obj
        except ValueError:
            return False

    def __repr__(self):
        gw = self.gateway or "directly connected"
        return f"Route({self.network} via {gw} dev {self.interface} proto={self.proto} metric={self.metric})"


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
        """Longest Prefix Match (RFC 1812 §5.2.4.3). Tie-break by metric."""
        matching = [r for r in self.routes if r.matches(dest_ip)]
        if not matching:
            return None
        matching.sort(key=lambda r: (-r.prefix_len, r.metric))
        return matching[0]

    def get_all_matching_routes(self, dest_ip: str) -> list[Route]:
        matching = [r for r in self.routes if r.matches(dest_ip)]
        matching.sort(key=lambda r: (-r.prefix_len, r.metric))
        return matching

    def add_route(self, network: str, gateway: Optional[str], interface: str,
                  metric: int = 1, proto: str = "static") -> None:
        norm = str(ipaddress.ip_network(network, strict=False))
        self.routes = [r for r in self.routes
                       if str(ipaddress.ip_network(r.network, strict=False)) != norm]
        self.routes.append(Route(norm, gateway, interface, metric, proto))

    def del_route(self, network: str) -> bool:
        norm = str(ipaddress.ip_network(network, strict=False))
        for r in self.routes:
            if str(ipaddress.ip_network(r.network, strict=False)) == norm:
                self.routes.remove(r)
                return True
        return False

    def get_interface_for_gateway(self, gateway_ip: str) -> Optional[Interface]:
        try:
            gw = ipaddress.ip_address(gateway_ip)
        except ValueError:
            return None
        for iface in self.interfaces:
            if gw in ipaddress.ip_network(iface.cidr, strict=False):
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
        self.links: list[tuple[str, str, str, str]] = []

    def add_device(self, device: NetworkDevice):
        self.devices[device.name] = device

    def add_link(self, dev_a: str, iface_a: str, dev_b: str, iface_b: str):
        self.links.append((dev_a, iface_a, dev_b, iface_b))

    def get_device_for_ip(self, ip: str) -> Optional[NetworkDevice]:
        for device in self.devices.values():
            for iface in device.interfaces:
                if iface.ip == ip:
                    return device
        return None

    def get_device_owning_network(self, network: str) -> Optional[NetworkDevice]:
        try:
            target_net = ipaddress.ip_network(network, strict=False)
        except ValueError:
            return None
        for device in self.devices.values():
            for iface in device.interfaces:
                if ipaddress.ip_network(iface.cidr, strict=False) == target_net:
                    return device
        return None

    def simulate_ping(self, src_name: str, dest_ip: str) -> list[HopResult]:
        hops: list[HopResult] = []
        visited: set[str] = set()
        MAX_HOPS = 30

        current_device = self.devices.get(src_name)
        if current_device is None:
            return [HopResult(src_name, "?", False, f"source '{src_name}' not found")]
        if not current_device.interfaces:
            return [HopResult(src_name, "?", False, "source has no interfaces")]
        src_ip = current_device.interfaces[0].ip

        try:
            ipaddress.ip_address(dest_ip)
        except ValueError:
            return [HopResult(src_name, src_ip, False, f"invalid destination: {dest_ip}")]

        hop_count = 0
        while hop_count < MAX_HOPS:
            hop_count += 1

            for iface in current_device.interfaces:
                if iface.ip == dest_ip:
                    hops.append(HopResult(current_device.name, iface.ip, True, "destination reached!"))
                    return hops

            visit_key = f"{current_device.name}:{dest_ip}"
            if visit_key in visited:
                hops.append(HopResult(current_device.name, src_ip, False, "ROUTING LOOP - packet discarded"))
                return hops
            visited.add(visit_key)

            route = current_device.lookup_route(dest_ip)
            if route is None:
                hops.append(HopResult(current_device.name, src_ip, False, f"NO ROUTE TO {dest_ip} - packet dropped"))
                return hops

            if route.gateway is None or route.proto == "connected":
                iface = current_device.get_interface_by_name(route.interface)
                iface_ip = iface.ip if iface else src_ip
                hops.append(HopResult(current_device.name, iface_ip, True,
                                      f"directly connected, delivering via {route.interface}"))
                dest_device = self.get_device_for_ip(dest_ip)
                if dest_device is None:
                    hops.append(HopResult("Host", dest_ip, True, "destination reached!"))
                    return hops
                current_device = dest_device
                src_ip = dest_ip
                continue

            gateway_ip = route.gateway
            iface = current_device.get_interface_by_name(route.interface)
            iface_ip = iface.ip if iface else src_ip
            hops.append(HopResult(current_device.name, iface_ip, True,
                                  f"forwarding to {gateway_ip} via {route.interface}"))

            next_device = self.get_device_for_ip(gateway_ip)
            if next_device is None:
                hops.append(HopResult("?", gateway_ip, False,
                                      f"next-hop {gateway_ip} unreachable"))
                return hops

            current_device = next_device
            src_ip = gateway_ip

        hops.append(HopResult("?", dest_ip, False, f"TTL exceeded after {MAX_HOPS} hops"))
        return hops
