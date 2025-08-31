######## INSTALAR Y USAR PYTHON 3.12 : 
sudo apt update
sudo apt install software-properties-common -y
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.12 python3.12-venv 
######## CREAR VIRTUAL ENVIRONMENT: 
python3.12 -m venv .venv
source .venv/bin/activate
######## RESTAURAR EN UN ENTORNO: 
pip install -r requirements.txt
