from unittest import TestSuite, defaultTestLoader, TextTestRunner


def main():
    suite = TestSuite()

    for i in defaultTestLoader.discover("cryptowelder_test", pattern="test_*.py"):
        suite.addTest(i)

    TextTestRunner().run(suite)


if __name__ == "__main__":
    main()
