#!/data/data/com.termux/files/usr/bin/sh
# Android (Termux) one-time setup. Install Termux from F-Droid, then:  sh termux_setup.sh
set -e
pkg update -y
pkg install -y python python-numpy
pip install requests || true
pip install pandas || { pkg install -y tur-repo && pkg install -y python-pandas; }
python -c "import numpy, pandas, requests; print('OK: packages ready')"
echo "Now run:  sh termux_run.sh"
