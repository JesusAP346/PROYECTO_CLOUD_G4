###### INSTALAR Y USAR PYTHON 3.12 : 
sudo apt update
sudo apt install software-properties-common -y
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.12 python3.12-venv 
###### CREAR VIRTUAL ENVIRONMENT: 
python3.12 -m venv .venv
source .venv/bin/activate
###### Guardar dependencias:
pip freeze > requirements.txt
###### RESTAURAR EN UN ENTORNO: 
pip install -r requirements.txt
###### Usar github:
sudo apt install git
git --version
git config --global user.name "Nombre"
git config --global user.email "correo"
##### Instalar postgresql
sudo apt install -y postgresql-common
sudo /usr/share/postgresql-common/pgdg/apt.postgresql.org.sh
sudo apt update
sudo apt install -y postgresql
echo "deb http://apt-archive.postgresql.org/pub/repos/apt focal-pgdg main" | sudo tee /etc/apt/sources.list.d/pgdg.list
sudo apt install -y postgresql-client-16
psql --version
