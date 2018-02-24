#!/usr/bin/env python

import cryptowelder


def main():
    context = cryptowelder.Context(config='~/.cryptowelder', read_only=False, debug=False)
    context.launch_prometheus()

    cryptowelder.BitbankWelder(context).run()
    cryptowelder.BitflyerWelder(context).run()
    cryptowelder.BtcboxWelder(context).run()
    cryptowelder.CoincheckWelder(context).run()
    cryptowelder.QuoinexWelder(context).run()


if __name__ == '__main__':
    main()
