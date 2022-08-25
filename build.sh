#=========================
# Run this in anaconda3
#=========================

source ~/anaconda3/etc/profile.d/conda.sh

VERSION=0.1.4

#32bit
export CONDA_FORCE_32BIT=1
conda create -n qget32 -y
conda activate qget32
conda install pip -y
pip install -r requirements.txt
pip install pyinstaller
pyinstaller --onefile --name=qget-$VERSION-i386 ./qget/__main__.py
conda deactivate
export CONDA_FORCE_32BIT=

#64bit
conda create -n qget64 -y
conda activate qget64
conda install pip -y
pip install -r requirements.txt
pip install pyinstaller
pyinstaller --onefile --name=qget-$VERSION-amd64 ./qget/__main__.py
conda deactivate
