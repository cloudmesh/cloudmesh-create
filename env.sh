# dont forget to call deactivate before calling it
deactivate
rm -fr ~/ENVy
python3 -m venv ~/ENVy
source ~/ENVy/bin/activate
pip install pip -U
pip install cloudmesh-cmd5
cms help
make local
cms help
