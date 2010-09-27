prefix=/usr/local
LIBDIR=$(prefix)/lib
BINDIR=$(prefix)/bin
DATADIR=$(prefix)/share
LOCALEDIR=$(DATADIR)/locale
MANDIR=$(DATADIR)/man
INSTALL=/bin/install
CP=/bin/cp
CHMOD=/bin/chmod

all: Makefile

clean:
	find ./ -name \*.pyc -delete
	find ./ -name \*~ -delete
	find ./ -name "#*#" -delete

install:
	mkdir -p $(DESTDIR)
	$(INSTALL) -d $(DESTDIR)$(LOCALEDIR) $(DESTDIR)$(BINDIR) $(DESTDIR)$(DATADIR)/poezio $(DESTDIR)$(DATADIR)/poezio/data $(DESTDIR)$(DATADIR)/poezio/src/ $(DESTDIR)$(DATADIR)/poezio/src/xmpp $(DESTDIR)$(DATADIR)/poezio/data/themes $(DESTDIR)$(MANDIR)/man1

	$(CP) -R data/* $(DESTDIR)$(DATADIR)/poezio/data/
	rm $(DESTDIR)$(DATADIR)/poezio/data/poezio.1
	$(CHMOD) 655 -R $(DESTDIR)$(DATADIR)/poezio/data/

	$(INSTALL) -m655 data/poezio.1 $(DESTDIR)$(MANDIR)/man1/
	for sourcefile in `find src/ -maxdepth 1 -type f -name \*.py` ; do \
		$(INSTALL) -m655 $$sourcefile $(DESTDIR)$(DATADIR)/poezio/src; \
	done

	echo "#!/usr/bin/env sh" > $(DESTDIR)$(BINDIR)/poezio
	echo "python3 $(DATADIR)/poezio/src/poezio.py" >> $(DESTDIR)$(BINDIR)/poezio
	chmod 755 $(DESTDIR)$(BINDIR)/poezio

uninstall:
	rm -f $(DESTDIR)$(BINDIR)/poezio
	rm -rf $(DESTDIR)$(DATADIR)/poezio
	rm -rf $(DESTDIR)$(MANDIR)/man1/poezio.1

pot:
	xgettext src/*.py --from-code=utf-8 --keyword=_ -o locale/poezio.pot
