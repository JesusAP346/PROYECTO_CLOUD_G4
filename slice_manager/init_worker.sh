#!/bin/bash

nombreOvs=$1
shift

if ! sudo ovs-vsctl list-br | grep -qw "$nombreOvs"; then
    #creamos ovs:
    sudo ovs-vsctl --may-exist add-br "$nombreOvs"
    #levantamos el ovs:
    sudo ip link set "$nombreOvs" up
fi

for interfazAConectar in "$@"; do
    #conectamos interfaz del worker
    sudo ovs-vsctl --may-exist add-port "$nombreOvs" "$interfazAConectar"
    #levantamos interfaz
    sudo ip link set dev "$interfazAConectar" up
done

