#!/usr/bin/env python

import cryptowelder


def main():
    context = cryptowelder.Context(config='~/.cryptowelder', read_only=False, debug=False)
    context.launch_prometheus()

    cryptowelder.BinanceWelder(context).run()
    cryptowelder.BitbankWelder(context).run()
    cryptowelder.BitfinexWelder(context).run()
    cryptowelder.BitflyerWelder(context).run()
    cryptowelder.BitmexWelder(context).run()
    cryptowelder.BitpointWelder(context).run()
    cryptowelder.BtcboxWelder(context).run()
    cryptowelder.CoincheckWelder(context).run()
    cryptowelder.FiscoWelder(context).run()
    cryptowelder.GmoCoinWelder(context).run()
    cryptowelder.HuobiJapanWelder(context).run()
    cryptowelder.KucoinWelder(context).run()
    cryptowelder.OandaWelder(context).run()
    cryptowelder.OkexWelder(context).run()
    cryptowelder.PoloniexWelder(context).run()
    cryptowelder.QuoinexWelder(context).run()
    cryptowelder.ZaifWelder(context).run()

    cryptowelder.MetricWelder(context).run()


if __name__ == '__main__':
    main()
