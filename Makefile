TMPDIR=/tmp/

all: Makefile
	python3 setup.py build_ext --inplace

clean:
	find ./ -name \*.pyc -delete
	find ./ -name \*.pyo -delete
	find ./ -name \*~ -delete
	find ./ -type d -name __pycache__ -delete
	find ./ -name "#*#" -delete
	rm -rf doc/build/
	rm -rf poezio.egg-info
	rm -rf dist
	rm -rf build
	rm -f poezio/*.so

install: all
	python3 setup.py install --root=$(DESTDIR) --optimize=1

doc:
	make -C doc/ html

test:
	py.test -v test/

release:
	rm -fr $(TMPDIR)/poezio-$(version)
	git clone $(PWD) $(TMPDIR)/poezio-$(version)
	cd $(TMPDIR)/poezio-$(version) && \
	 git checkout v$(version) && \
	 make doc && \
	 cd .. && \
	 tar cJf poezio-$(version).tar.xz poezio-$(version) && \
	 tar czf poezio-$(version).tar.gz poezio-$(version)

.PHONY : doc test
