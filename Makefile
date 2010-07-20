prefix=/usr/local
LIBDIR=$(prefix)/lib
BINDIR=$(prefix)/bin
DATADIR=$(prefix)/share
LOCALEDIR=$(DATADIR)/locale
MANDIR=$(DATADIR)/man
INSTALL=install

all: Makefile

clean:
	find ./ -name \*.pyc -delete
	find ./ -name \*~ -delete

install:
	$(INSTALL) -d $(BINDIR) $(DATADIR)/poezio $(DATADIR)/poezio/data $(DATADIR)/poezio/src $(DATADIR)/poezio/src/

	$(INSTALL) -m644 data/* $(DESTDIR)$(DATADIR)/poezio/data/

	for sourcefile in `find src/ -maxdepth 1 -type f -name \*.py` ; do \
		$(INSTALL) -m644 $$sourcefile $(DESTDIR)$(DATADIR)/poezio/src; \
	done

	echo "#!/usr/bin/env sh" > $(DESTDIR)$(BINDIR)/poezio
	echo "cd $(DATADIR)/poezio/src/ && python poezio.py" >> $(DESTDIR)$(BINDIR)/poezio
	chmod 755 $(DESTDIR)$(BINDIR)/poezio

uninstall:
	rm -f $(DESTDIR)$(BINDIR)/poezio
	rm -rf $(DESTDIR)$(DATADIR)/poezio

pot:
	xgettext src/*.py --from-code=utf-8 --keyword=_ -o locale/poezio.pot
