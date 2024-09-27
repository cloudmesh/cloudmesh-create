# dont forget to call deactivate before calling it
deactivate
rm -fr ~/ENV3
py  -m venv ~/ENV3
source ~/ENV3/Scripts/activate
py -m pip install pip -U
py -m pip install cloudmesh-cmd5
cms help
make local
cms help
