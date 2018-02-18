#!/usr/bin/env python

import cryptowelder


def main():
    context = cryptowelder.Context(read_only=False, config='~/.cryptowelder')
    context.launch_prometheus()

    cryptowelder.BitflyerWelder(context).run()


if __name__ == '__main__':
    main()
