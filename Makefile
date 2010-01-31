prefix=/usr
LIBDIR=$(DESTDIR)$(prefix)/lib
BINDIR=$(DESTDIR)$(prefix)/bin
DATADIR=$(DESTDIR)$(prefix)/share
LOCALEDIR=$(DATADIR)/locale
MANDIR=$(DATADIR)/man
INSTALL=install

all: 	Makefile
clean:	Makefile

install:
	$(INSTALL) -d $(LOCALEDIR) $(BINDIR) $(DATADIR)/poezio $(DATADIR)/poezio/data $(DATADIR)/poezio/src

	$(INSTALL) -m644 data/* $(DATADIR)/poezio/data/

	for sourcefile in `find src/ -maxdepth 1 -type f | grep -v '.svn' | grep -v '.pyc'` ; do \
		$(INSTALL) -m644 $$sourcefile $(DATADIR)/poezio/src; \
	done

	echo "#!/bin/sh" > $(BINDIR)/poezio
	echo "cd $(DATADIR)/poezio/src/ && python client.py" >> $(BINDIR)/poezio
	chmod 755 $(BINDIR)/poezio

	for localename in `find locale/ -maxdepth 1 -type d | grep -v '.svn' | sed 's:locale/::g'` ; do \
		if [ -d locale/$$localename ]; then \
		    $(INSTALL) -d $(LOCALEDIR)/$$localename; \
		    $(INSTALL) -d $(LOCALEDIR)/$$localename/LC_MESSAGES; \
			msgfmt locale/$$localename/LC_MESSAGES/poezio.po -o locale/$$localename/LC_MESSAGES/poezio.mo -v; \
			$(INSTALL) -m644 locale/$$localename/LC_MESSAGES/poezio.mo $(LOCALEDIR)/$$localename/LC_MESSAGES; \
		fi \
	done

uninstall:
	rm -f $(BINDIR)/poezio
	rm -rf $(DATADIR)/poezio

	for gettextfile in `find $(LOCALEDIR) -name 'poezio.mo'` ; do \
		rm -f $$gettextfile; \
	done

pot:
	xgettext src/*.py --from-code=utf-8 --keyword=_ -o locale/poezio.pot
