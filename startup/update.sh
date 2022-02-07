#!/bin/bash
sudo -u theycantalk git checkout -f main
t=`git branch -r --sort=committerdate | tail -1`
a=`git rev-parse $t`
b=`git rev-parse HEAD`
if [ "$a" != "$b" ]; then
	checkout=$?
	sudo -u theycantalk git pull
	pull=$?
	cd .. && make clean && sudo -u theycantalk make build
	build=$?
	if [ -f /mnt/log.txt ]; then
		if [ $checkout -eq 0 ]; then
			echo "successfully checkout latest version" >> /mnt/log.txt
		else
			echo "failed to checkout latest version" >> /mnt/log.txt
		fi
		if [ $pull -eq 0 ]; then
			echo "successfully download latest version" >> /mnt/log.txt
		else
			echo "failed to download latest version" >> /mnt/log.txt
		fi
		if [ $build -eq 0 ]; then
			echo "successfully build latest version" >> /mnt/log.txt
		else
			echo "failed build latest version" >> /mnt/log.txt
		fi
	fi
else
	echo "up to date"
fi