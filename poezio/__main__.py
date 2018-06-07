def run():
    from poezio.poezio import main, test_curses, test_env, test_unicode

    if not test_curses() or not test_env() or not test_unicode():
        import sys
        sys.exit(1)
    else:
        main()
    return 0


if __name__ == '__main__':
    run()
