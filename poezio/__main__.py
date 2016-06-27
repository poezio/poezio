from poezio.poezio import test_curses, main

if test_curses():
    main()
else:
    sys.exit(1)
