#!/bin/bash

#GRUPO 4 --> LINUX CLUSTER --> 10.60.7.0/24

nombreNS=$1
nombreOvs=$2
vlanID=$3
rangoDHCP=$4 #formato: IP_inicio,IP_fin,MASCARA     ejemplo: 10.0.0.10,10.0.0.13,255.255.255.248
defaultGateway=$5 #formato: IP_gateway     ejemplo: 10.0.0.9        consideracion: la primera IP de la red sera gateway.  Ultima IP será de la ip de namespace



#Parseamos el rango dado de DHCP
IFS=',' read -r ipStart ipEnd netmask <<< "$rangoDHCP"
# Tabla de conversión netmask → CIDR
declare -A NETMASK_TO_CIDR=(
  ["255.255.255.255"]=32
  ["255.255.255.254"]=31
  ["255.255.255.252"]=30
  ["255.255.255.248"]=29
  ["255.255.255.240"]=28
  ["255.255.255.224"]=27
  ["255.255.255.192"]=26
  ["255.255.255.128"]=25
  ["255.255.255.0"]=24
  ["255.255.254.0"]=23
  ["255.255.252.0"]=22
  ["255.255.248.0"]=21
  ["255.255.240.0"]=20
  ["255.255.224.0"]=19
  ["255.255.192.0"]=18
  ["255.255.128.0"]=17
  ["255.255.0.0"]=16
)

cidr="${NETMASK_TO_CIDR[$netmask]}"





# Calcular red 
if command -v python3 >/dev/null 2>&1; then
  subnetCIDR=$(python3 - <<PY
import ipaddress
gw = ipaddress.ip_interface("$defaultGateway/$cidr")
print(f"{gw.network.network_address}/{gw.network.prefixlen}")
PY
)
elif command -v ipcalc >/dev/null 2>&1; then
  # ipcalc a veces devuelve "Network: 10.0.0.8/29" o "NETWORK=10.0.0.8/29"
  net_line=$(ipcalc -n "$defaultGateway/$cidr" | grep -i 'network')
  # extrae "10.0.0.8/29" sin la etiqueta
  subnetCIDR=$(echo "$net_line" | sed 's/.*[Nn][Ee][Tt][Ww][Oo][Rr][Kk][^0-9]*//')
else
  # Fallback (asume /24 para aproximar el .0); menos preciso, pero operativo
  subnetCIDR="${defaultGateway%.*}.0/$cidr"
fi

# Calcular nsIP como la última IP usable del subnetCIDR
if command -v python3 >/dev/null 2>&1; then
  nsIP=$(python3 - <<PY
import ipaddress
net = ipaddress.ip_network("$subnetCIDR", strict=False)
print(list(net.hosts())[-1])
PY
)
elif command -v ipcalc >/dev/null 2>&1; then
  # host range: "Hosts/Net: x  10.0.0.9 - 10.0.0.14"
  last=$(ipcalc -h "$subnetCIDR" | awk -F- '/Host/ {gsub(/ /,""); print $2}')
  nsIP="$last"
else
  echo "No hay python3 ni ipcalc para derivar nsIP. Pásalo como 6to parámetro o instala uno de ellos."
  exit 1
fi



#creamos el namespace que funcionara como dhcp:
if ip netns list | awk '{print $1}' | grep -qx "$nombreNS"; then
  echo "Namespace $nombreNS ya existe, continuando…"
else
  sudo ip netns add "$nombreNS"
fi

#creamos el ovs
if ! sudo ovs-vsctl list-br | grep -qw "$nombreOvs"; then
    #creamos ovs:
    sudo ovs-vsctl --may-exist add-br "$nombreOvs"
    #levantamos el OVS    
    sudo ip link set "$nombreOvs" up
fi


#Configurar la interfaz del namespace como interfaz interna
#sudo ovs-vsctl add-port "$nombreOvs" ovs-tap0 -- set interface ovs-tap0 type=internal


# Creamos path veth :
veth_extremo_ns="vns${vlanID}"
veth_extremo_ovs="vbr${vlanID}"

# Si el extremo del NS existe dentro del namespace, lo borramos
if ip netns exec "$nombreNS" ip link show "$veth_extremo_ns" &>/dev/null; then
  sudo ip netns exec "$nombreNS" ip link del "$veth_extremo_ns" || true
fi
# Si el extremo del host existe, lo borramos.
if ip link show "$veth_extremo_ovs" &>/dev/null; then
  sudo ip link del "$veth_extremo_ovs" || true
fi
# Por si acaso el nombre del lado NS quedó en el host 
if ip link show "$veth_extremo_ns" &>/dev/null; then
  sudo ip link del "$veth_extremo_ns" || true
fi


sudo ip link show "$veth_extremo_ns" >/dev/null 2>&1 && sudo ip link del "$veth_extremo_ns" || true
sudo ip link add "$veth_extremo_ns" type veth peer name "$veth_extremo_ovs"

#Asignar extremo de interfaz al namespace
sudo ip link set "$veth_extremo_ns" netns "$nombreNS"

#asignamos otro extremo al ovs con la vlan
sudo ovs-vsctl --may-exist add-port "$nombreOvs" "$veth_extremo_ovs" tag="$vlanID"


#encendemos las interfaces del namespace
sudo ip netns exec "$nombreNS" ip link set dev lo up
sudo ip netns exec "$nombreNS" ip link set dev "$veth_extremo_ns" up
sudo ip link set "$veth_extremo_ovs" up




#configuramos la interfaz del namespace con una ip dentro del rango
sudo ip netns exec "$nombreNS" ip address flush dev "$veth_extremo_ns"
sudo ip netns exec "$nombreNS" ip address add "$nsIP/$cidr" dev "$veth_extremo_ns"
sudo ip netns exec "$nombreNS" ip route replace default via "$defaultGateway"

#Configuramos interfaz interna del switch OvS con una IP dentro del rango para q sea el gateway 
#if ! ip addr show dev "$nombreOvs" | grep -q "$defaultGateway/$cidr"; then
#  sudo ip address add "$defaultGateway/$cidr" dev "$nombreOvs"
#fi

#asignamos gateway en el OvS para la VLAN
gw_if="gw${vlanID}"
# crea puerto interno + tag VLAN (interfaz L3 por VLAN)

sudo ovs-vsctl --if-exists del-port "$nombreOvs" "$gw_if"
sudo ovs-vsctl add-port "$nombreOvs" "$gw_if" -- set Port "$gw_if" tag="$vlanID" -- set Interface "$gw_if" type=internal
sudo ip link set "$gw_if" up
sudo ip addr flush dev "$gw_if" || true
sudo ip addr add "$defaultGateway/$cidr" dev "$gw_if"




#configuramos el servidor DHCP
#sudo ip netns exec "$nombreNS" dnsmasq --interface="$veth_extremo_ns" --dhcp-range="$ipStart,$ipEnd,$netmask" --dhcp-option=3,"$defaultGateway"
sudo ip netns exec "$nombreNS" dnsmasq \
  --interface="$veth_extremo_ns" \
  --bind-interfaces \
  --port=0 \
  --dhcp-authoritative \
  --dhcp-range="$ipStart,$ipEnd,$netmask,12h" \
  --dhcp-option=3,"$defaultGateway" \
  --pid-file=/var/run/dnsmasq-"$nombreNS".pid

# REGLAS DE NAT + FORWARD

#habilitamos reenvío de paquetes
sudo sysctl -w net.ipv4.ip_forward=1


#configuramos regla NAT MASQUERADE
#sudo iptables -t nat -D POSTROUTING -s "$subnetCIDR" -j MASQUERADE 2>/dev/null || true
#sudo iptables -t nat -A POSTROUTING -s "$subnetCIDR" -j MASQUERADE

#sudo iptables -D FORWARD -i "$nombreOvs" -j ACCEPT 2>/dev/null || true
#sudo iptables -D FORWARD -o "$nombreOvs" -j ACCEPT 2>/dev/null || true
#sudo iptables -A FORWARD -i "$nombreOvs" -j ACCEPT
#sudo iptables -A FORWARD -o "$nombreOvs" -j ACCEPT
