#!/bin/bash

nombreOvs=$1
shift

if ! sudo ovs-vsctl list-br | grep -qw "$nombreOvs"; then
    #creamos ovs:
    sudo ovs-vsctl --may-exist add-br "$nombreOvs"
    #levantamos el OVS    
    sudo ip link set "$nombreOvs" up
fi


for interfaz in "$@"; do
    #limpiamos la configuracion IP de la red Data Network
    sudo ip address flush dev "$interfaz"

    #levantamos la interfaz
    sudo ip link set dev "$interfaz" up

    #conectamos agregamos las interfaces al ovs
    sudo ovs-vsctl --may-exist add-port "$nombreOvs" "$interfaz"

done


# Activar IPv4 forwarding 
sudo sysctl -w net.ipv4.ip_forward=1
# Cambiar política por defecto de FORWARD a DROP
sudo iptables -P FORWARD DROP
