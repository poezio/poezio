def run():
    from poezio.poezio import test_curses, main

    if test_curses():
        main()
    else:
        import sys
        sys.exit(1)
    return 0
