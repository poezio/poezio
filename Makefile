prefix=/usr/local
LIBDIR=$(DESTDIR)$(prefix)/lib
BINDIR=$(DESTDIR)$(prefix)/bin
DATADIR=$(DESTDIR)$(prefix)/share
LOCALEDIR=$(DATADIR)/locale
MANDIR=$(DATADIR)/man
INSTALL=install

all:
	cd src/xmpppy-0.5.0rc1 && pwd && python setup.py build && cp -r xmpp ..

clean:	Makefile

install:
	$(INSTALL) -d $(LOCALEDIR) $(BINDIR) $(DATADIR)/poezio $(DATADIR)/poezio/data $(DATADIR)/poezio/src $(DATADIR)/poezio/src/

	$(INSTALL) -m644 data/* $(DATADIR)/poezio/data/

	for sourcefile in `find src/ -maxdepth 1 -type f -name \*.py'` ; do \
		$(INSTALL) -m644 $$sourcefile $(DATADIR)/poezio/src; \
	done
	$(INSTALL) -m644 src/xmpp/* $(DATADIR)/poezio/src/xmpp/

	echo "#!/usr/bin/env sh" > $(BINDIR)/poezio
	echo "cd $(DATADIR)/poezio/src/ && python poezio.py" >> $(BINDIR)/poezio
	chmod 755 $(BINDIR)/poezio

uninstall:
	rm -f $(BINDIR)/poezio
	rm -rf $(DATADIR)/poezio

pot:
	xgettext src/*.py --from-code=utf-8 --keyword=_ -o locale/poezio.pot
