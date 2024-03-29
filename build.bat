::=========================
:: Run this in anaconda3
::=========================

set VERSION=0.1.7

::32bit
set CONDA_FORCE_32BIT=1
call conda create -n qget32 python=3.10.4 -y
call conda activate qget32
call conda install pip -y
pip install -r requirements.txt
pip install pyinstaller
pyinstaller --onefile --name=qget-%VERSION%-win32 .\qget\__main__.py
call conda deactivate
set CONDA_FORCE_32BIT=

::64bit
call conda create -n qget64 python=3.10.6 -y
call conda activate qget64
call conda install pip -y
pip install -r requirements.txt
pip install pyinstaller
pyinstaller --onefile --name=qget-%VERSION%-win_amd64 .\qget\__main__.py
call conda deactivate
