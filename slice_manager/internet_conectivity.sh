#!/bin/bash
vlanID=$1
uplink="ens3"

gw_if="gw${vlanID}"
bridge="$(sudo ovs-vsctl iface-to-br "$gw_if" 2>/dev/null || true)"
gw_cidr="$(ip -o -f inet addr show "$gw_if" | awk '{print $4}' | head -n1)"

#obtenemos subetcidr
if command -v python3 >/dev/null 2>&1; then
  subnetCIDR=$(python3 - <<PY
import ipaddress
iface = ipaddress.ip_interface("$gw_cidr")
print(str(iface.network))
PY
)
else
  net_line=$(ipcalc -n "$gw_cidr" | grep -i 'network')
  subnetCIDR=$(echo "$net_line" | sed 's/.*[Nn][Ee][Tt][Ww][Oo][Rr][Kk][^0-9]*//')
fi

sudo sysctl -w net.ipv4.ip_forward=1 

# NAT por subred (borra antes de agregar) 
sudo iptables -t nat -D POSTROUTING -s "$subnetCIDR" -o "$uplink" -j MASQUERADE 2>/dev/null || true
sudo iptables -t nat -A POSTROUTING -s "$subnetCIDR" -o "$uplink" -j MASQUERADE

#Reglas NEW/ESTABLISHED,RELATED hacia afuera y sólo ESTABLISHED,RELATED de vuelta
sudo iptables -D FORWARD -i "$gw_if" -o "$uplink" -m state --state NEW,ESTABLISHED,RELATED -j ACCEPT 2>/dev/null || true
sudo iptables -D FORWARD -i "$uplink" -o "$gw_if" -m state --state ESTABLISHED,RELATED -j ACCEPT 2>/dev/null || true
sudo iptables -A FORWARD -i "$gw_if" -o "$uplink" -m state --state NEW,ESTABLISHED,RELATED -j ACCEPT
sudo iptables -A FORWARD -i "$uplink" -o "$gw_if" -m state --state ESTABLISHED,RELATED -j ACCEPT