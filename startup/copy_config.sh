#!/bin/bash
drive=`fdisk -l | grep -E "exFAT|NFTS" | cut -d " " -f1`
if [ -e $drive ]; then
	mount $drive /mnt || mount /dev/sda /mnt || mount /dev/sdb /mnt
	echo "successfully mounted $drive to device" > /mnt/log.txt
	# test config exists
	if [ -f /mnt/log.txt ]; then
		echo "blah" > /dev/null
	else
		echo "config.json not found!" >> /mnt/log.txt
	fi
	# test config is properly formatted
	jq -r '.["email"]' /mnt/config.json
	if [ $? -eq 0 ]; then
		echo "config.json is formatted properly" >> /mnt/log.txt
	else
		echo "json config is improperly formatted. Contact jack@theycantalk.org" >> /mnt/log.txt
	fi
	# copy it over and if it works, we might as well try to boot the internet
	cp /mnt/config.json /srv/beholder_configuration/config.json
	if [ $? -eq 0 ]; then
		echo "successfully copied config.json to device" >> /mnt/log.txt
		sh /home/theycantalk/beholder/startup/wifi.sh
	else
		echo "failed to copy your config to device. Contact jack@theycantalk.org" >> /mnt/log.txt
	fi
fi
