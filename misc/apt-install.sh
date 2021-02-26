#!/bin/sh

export DEBIAN_FRONTEND=noninteractive

echo steam steamcmd/question select "I AGREE" | debconf-set-selections
echo steam steamcmd/license note '' | debconf-set-selections

dpkg --add-architecture i386
apt update
apt -y dist-upgrade
apt -y install openssl git steamcmd tmux sudo curl htop haveged libsdl2-2.0-0
