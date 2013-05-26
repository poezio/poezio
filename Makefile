prefix=/usr/local
LIBDIR=$(prefix)/lib
BINDIR=$(prefix)/bin
DATADIR=$(prefix)/share
DOCDIR=$(DATADIR)/doc
LOCALEDIR=$(DATADIR)/locale
MANDIR=$(DATADIR)/man

all: Makefile
	python3 setup.py build_ext --inplace

clean:
	find ./ -name \*.pyc -delete
	find ./ -name \*.pyo -delete
	find ./ -name \*~ -delete
	find ./ -name "#*#" -delete
	rm -r doc/build/

install: all
	mkdir -p $(DESTDIR)$(prefix)  $(DESTDIR)$(DOCDIR)/poezio/ $(DESTDIR)$(LOCALEDIR) $(DESTDIR)$(BINDIR)

	cp -R doc/* $(DESTDIR)$(DOCDIR)/poezio/

	cp README CHANGELOG COPYING $(DESTDIR)$(DOCDIR)/poezio/

uninstall:
	rm -f $(DESTDIR)$(BINDIR)/poezio
	rm -rf $(DESTDIR)$(DATADIR)/poezio
	rm -rf $(DESTDIR)$(MANDIR)/man1/poezio.1

doc:
	make -C doc/ html
pot:
	xgettext src/*.py --from-code=utf-8 --keyword=_ -o locale/poezio.pot

.PHONY : doc
