###### INSTALAR Y USAR PYTHON 3.12 : 
sudo apt update
sudo apt install software-properties-common -y
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.12 python3.12-venv 
###### CREAR VIRTUAL ENVIRONMENT: 
python3.12 -m venv .venv
source .venv/bin/activate
###### GUARDAR DEPENDENCIAS:
pip freeze > requirements.txt
###### RESTAURAR EN UN ENTORNO: 
pip install -r requirements.txt
###### USAR GITHUB:
sudo apt install git
git --version
git config --global user.name "Nombre"
git config --global user.email "correo"
###### INSTALAR PostgreSQL
sudo apt install -y postgresql-common
sudo /usr/share/postgresql-common/pgdg/apt.postgresql.org.sh
sudo apt update
sudo apt install -y postgresql
echo "deb http://apt-archive.postgresql.org/pub/repos/apt focal-pgdg main" | sudo tee /etc/apt/sources.list.d/pgdg.list
sudo apt install -y postgresql-client-16
sudo apt install -y postgresql-16
sudo pg_upgradecluster 12 main
pg_lsclusters
###### VALIDAR PostgreSQL y CONFIGURAR
psql --version
sudo -u postgres psql
ALTER USER postgres WITH PASSWORD 'password';
###### EDITAR EL SIGUIENTE ARCHIVO Y AGREGAR: listen_addresses = '*'
sudo nano /etc/postgresql/16/main/postgresql.conf  
###### EDITAR EL SIGUIENTE ARCHIVO Y AGREGAR: host    all    all    0.0.0.0/0    md5
sudo nano /etc/postgresql/16/main/pg_hba.conf 
sudo systemctl restart postgresql

###### COMANDO PARA CREAR EL TUNEL SSH DESDE MI MAQUINA LOCAL: 
ssh -N -L 5433:127.0.0.1:5432 -p 5801 ubuntu@IP
