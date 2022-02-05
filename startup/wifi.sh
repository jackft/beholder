#!/bin/bash
file=/srv/beholder_configuration/config.json
network=`jq -r '.["network_name"]' $file`
password=`jq -r '.["network_password"]' $file`
echo "$network"
echo "$password"
nmcli dev wifi connect "$network" password "$password" ifname wlan0
sleep 10
if [ -f /mnt/log.txt ]; then
    wget -q --spider http://google.com
	if [ $? -eq 0 ]; then
		echo "successfully connected to internet" >> /mnt/log.txt
	else
		echo "failed to connect to internet. Double check the config." >> /mnt/log.txt
	fi
fi

