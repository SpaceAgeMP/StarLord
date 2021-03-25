#!/bin/sh

export DEBIAN_FRONTEND=noninteractive

echo steam steamcmd/question select "I AGREE" | debconf-set-selections
echo steam steamcmd/license note '' | debconf-set-selections

dpkg --add-architecture i386
apt update
apt -y dist-upgrade
apt -y install openssl git steamcmd tmux sudo curl htop haveged libsdl2-2.0-0 python3 python3-yaml python3-requests python3-pip

pip3 install python_a2s

sudo -u server1 mkdir -p /home/server1/s/garrysmod/lua/autorun/server /home/server1/s/garrysmod/cfg /home/server1/s/garrysmod/sa_config
