FROM steamcmd/steamcmd:ubuntu

RUN apt update && \
        apt -y dist-upgrade && \
        apt --no-install-recommends -y install python3 python3-requests python3-yaml python3-pip git openssh-client lsof libssl3 libboost-system1.74.0 rsync && \
        rm -rf /var/cache/apt
RUN pip3 install python_a2s

VOLUME /home/server

RUN groupadd server -g 1000 && \
        useradd server -u 1000 -g 1000 -s /bin/false && \
        mkdir -p /home/server && \
        chown -R server:server /home/server
USER server

ENV PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/games:/usr/local/game
ENV HOME=/home/server
ENV STARLORD_CONFIG=spaceage_gooniverse
ENV SPACEAGE_SERVER_TOKEN=
ENV ENABLE_SELF_UPDATE=false
ENV SRCDS_CMD_FIFO=/tmp/srcds.fifo

COPY . /opt/StarLord

ENTRYPOINT ["/opt/StarLord/misc/dockerboot.sh"]
