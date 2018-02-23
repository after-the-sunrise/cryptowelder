#!/usr/bin/env python

import cryptowelder


def main():
    context = cryptowelder.Context(config='~/.cryptowelder', read_only=False, debug=False)
    context.launch_prometheus()

    cryptowelder.BitflyerWelder(context).run()


if __name__ == '__main__':
    main()
