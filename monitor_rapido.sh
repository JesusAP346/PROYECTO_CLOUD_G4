#!/bin/bash

echo "=== 📊 MONITOREO RÁPIDO DEL SISTEMA ==="

# Estado
echo -e "\n=== 🔍 ESTADO ==="
curl -s 'http://localhost:9090/api/v1/query?query=up' | python3 -c "
import json
data = json.loads(input())
up_count = sum(1 for r in data['data']['result'] if r['value'][1] == '1')
print(f'Sistemas activos: {up_count}/{len(data[\"data\"][\"result\"])}')"

# Recursos en una sola consulta
echo -e "\n=== 📈 RECURSOS ==="
python3 << 'ENDPYTHON'
import json
import urllib.request
import urllib.parse

# Consulta CPU
cpu_query = '100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)'
cpu_data = json.loads(urllib.request.urlopen('http://localhost:9090/api/v1/query?' + urllib.parse.urlencode({'query': cpu_query})).read())

# Consulta Memoria
mem_query = '((node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes) * 100'
mem_data = json.loads(urllib.request.urlopen('http://localhost:9090/api/v1/query?' + urllib.parse.urlencode({'query': mem_query})).read())

# Consulta Disco
disk_query = '(1 - (node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"})) * 100'
disk_data = json.loads(urllib.request.urlopen('http://localhost:9090/api/v1/query?' + urllib.parse.urlencode({'query': disk_query})).read())

print(f"{'INSTANCIA':<20} {'CPU':<6} {'MEM':<6} {'DISCO':<6}")
print("-" * 45)

# Recolectar todos los instances
instances = set()
for data in [cpu_data, mem_data, disk_data]:
    for result in data.get('data', {}).get('result', []):
        instances.add(result['metric']['instance'])

# Mostrar datos por instance
for instance in sorted(instances):
    if '9100' in instance:  # Solo workers, no localhost
        # CPU
        cpu = next((float(r['value'][1]) for r in cpu_data.get('data', {}).get('result', []) if r['metric']['instance'] == instance), 0)
        # Memoria
        mem = next((float(r['value'][1]) for r in mem_data.get('data', {}).get('result', []) if r['metric']['instance'] == instance), 0)
        # Disco
        disk = next((float(r['value'][1]) for r in disk_data.get('data', {}).get('result', []) if r['metric']['instance'] == instance), 0)
        
        print(f"{instance:<20} {cpu:4.1f}% {mem:4.1f}% {disk:4.1f}%")

ENDPYTHON

echo -e "\n✅ Monitoreo completado"