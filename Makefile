.DEFAULT_GOAL := build
.PHONY: build

build: build_recorder build_webapp build_email

build_recorder:
	cd recorder && make build

build_webapp:
	cd webapp && make build

build_email:
	cd email && make build

clean: clean_recorder clean_webapp

clean_recorder:
	cd recorder && make clean

clean_webapp:
	cd webapp && make clean

