#=========================
# Run this in anaconda3
#=========================

#32bit
set CONDA_FORCE_32BIT=1
conda create -n qget32 -y
conda activate qget32
conda install pip -y
pip install -r requirements.txt
pip install pyinstaller
pyinstaller --onefile --name=qget32 ./qget/__main__.py
conda deactivate
set CONDA_FORCE_32BIT=

#64bit
conda create -n qget64 -y
conda activate qget64
conda install pip -y
pip install -r requirements.txt
pip install pyinstaller
pyinstaller --onefile --name=qget64 ./qget/__main__.py
conda deactivate
