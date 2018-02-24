#!/usr/bin/env python

import cryptowelder


def main():
    context = cryptowelder.Context(config='~/.cryptowelder', read_only=False, debug=False)
    context.launch_prometheus()

    cryptowelder.BitbankWelder(context).run()
    cryptowelder.BitfinexWelder(context).run()
    cryptowelder.BitflyerWelder(context).run()
    cryptowelder.BitmexWelder(context).run()
    cryptowelder.BtcboxWelder(context).run()
    cryptowelder.CoincheckWelder(context).run()
    cryptowelder.OandaWelder(context).run()
    cryptowelder.PoloniexWelder(context).run()
    cryptowelder.QuoinexWelder(context).run()
    cryptowelder.ZaifWelder(context).run()


if __name__ == '__main__':
    main()
