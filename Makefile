build:
	python3 setup.py install

install:
	pip3 install -r requirements.txt

clean:
	pip3 uninstall news-please -y && rm -rf ./build