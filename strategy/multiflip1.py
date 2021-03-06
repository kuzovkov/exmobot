#coding=utf-8

'''
Стратегия поиска валютных пар на которых есть профитный спред
и запуск на них стратегии циклического обмена flip3
'''

import strategy.flip3 as flip3
from pprint import pprint
import strategy.library.functions as Lib

class Strategy:

    capi = None
    logger = None
    storage = None
    conf = None
    params = None

    pair = None
    name = 'multiflip1'
    mode = 0
    session_id = 'default'
    min_profit = 0.005
    limit = 1000000000.0
    #префикс для логгера
    prefix = ''


    def __init__(self, capi, logger, storage, conf=None, **params):
        self.storage = storage
        self.capi = capi
        self.conf = conf
        self.logger = logger
        self.params = params
        self.prefix = capi.name + ' ' + self.name
        self.session_id = capi.name + '-' + self.name
        #ввод параметров
        #параметры передаваемые при вызове функции имеют приоритет
        #перед параметрами заданными в файле конфигурации


    '''
    функция реализующая торговую логику
    '''
    def run(self):
        self.logger.info('-' * 40, self.prefix)
        self.logger.info('Run strategy %s' % self.name, self.prefix)
        #минимальный объем торгов криптовалюты
        min_volume = Lib.set_param(self, key='min_volume', default_value=10.0, param_type='float')
        profit_pairs = self.get_profit_pairs()
        pairs = self.select_pairs(profit_pairs, min_volume)
        self.logger.info('Pairs for trading: %s' % str(map(lambda e: e['pair'], pairs)), self.prefix)
        #pprint(pairs)

        # сохраняем балансы в базу для сбора статистики
        balance_usd = self.capi.balance_full_usd()
        if self.capi.name == 'poloniex':
            self.save_change_balance('USDT', balance_usd)
        else:
            self.save_change_balance('USD', balance_usd)

        for pair in pairs:
            flip = flip3.Strategy(self.capi, self.logger, self.storage, self.conf, pair=pair['pair'])
            flip.run()


    '''
    поиск пар для профитной торговли
    '''
    def get_profit_pairs(self):
        fees = self.capi._get_fee()
        ticker = self.capi.ticker()
        base_valute = {'exmo': 0, 'btce':1, 'poloniex':0}
        #pprint(ticker)
        profit_pairs = []
        currency_ratio = {}
        for pair, data in ticker.items():
            if data['buy_price'] < data['sell_price']:
                buy_price = data['buy_price']
                sell_price = data['sell_price']
            else:
                buy_price = data['sell_price']
                sell_price = data['buy_price']
            fee = fees[pair]
            profit = sell_price / buy_price * (1-fee) * (1-fee) - 1
            currency_ratio[pair] = (sell_price + buy_price)/2
            vol_currency = pair.split('_')[base_valute[self.capi.name]]
            pair_info = {'pair':pair, 'profit':profit, 'vol': data['vol'], 'vol_btc': 0.0, 'vol_currency': vol_currency, 'sell_price':sell_price, 'buy_price':buy_price}
            if profit > 0:
                profit_pairs.append(pair_info)

        profit_pairs = sorted(profit_pairs, key=lambda row: 1/row['profit'])

        #pprint(currency_ratio)
        if self.capi.name == 'poloniex':
            for i in range(len(profit_pairs)):
                if profit_pairs[i]['vol_currency'] == 'BTC':
                    profit_pairs[i]['vol_btc'] = profit_pairs[i]['vol']
                elif ('BTC_' + profit_pairs[i]['vol_currency']) in currency_ratio:
                    profit_pairs[i]['vol_btc'] = profit_pairs[i]['vol'] * currency_ratio[('BTC_' + profit_pairs[i]['vol_currency'])]
                elif (profit_pairs[i]['vol_currency'] + '_BTC') in currency_ratio:
                    profit_pairs[i]['vol_btc'] = profit_pairs[i]['vol'] / currency_ratio[(profit_pairs[i]['vol_currency'] + '_BTC')]
                else:
                    profit_pairs[i]['vol_btc'] = 0.0
        else:
            for i in range(len(profit_pairs)):
                if profit_pairs[i]['vol_currency'] == 'BTC':
                    profit_pairs[i]['vol_btc'] = profit_pairs[i]['vol']
                elif ('BTC_' + profit_pairs[i]['vol_currency']) in currency_ratio:
                    profit_pairs[i]['vol_btc'] = profit_pairs[i]['vol'] / currency_ratio[('BTC_' + profit_pairs[i]['vol_currency'])]
                elif (profit_pairs[i]['vol_currency'] + '_BTC') in currency_ratio:
                    profit_pairs[i]['vol_btc'] = profit_pairs[i]['vol'] * currency_ratio[(profit_pairs[i]['vol_currency'] + '_BTC')]
                else:
                    profit_pairs[i]['vol_btc'] = 0.0

        return profit_pairs


    '''
    выбор пар для торговли из массива заданных пар
    @param profit_pairs список пар вида: [{'pair':pair, 'profit':profit, 'vol': data['vol'], 'vol_btc': 0.0, 'vol_currency': vol_currency, 'sell_price':sell_price, 'buy_price':buy_price}, ...]
    @param  vol_min минимальный объем торгов в BTC
    @param max_number максимальное количество пар в списке
    '''
    def select_pairs(self, profit_pairs, vol_min, max_number=10):
        result = []
        black_list = ['USD_RUR', 'EUR_USD', 'EUR_RUR']
        for pair_info in profit_pairs:
            if pair_info['vol_btc'] >= vol_min and pair_info['pair'] not in black_list:
                result.append(pair_info)
        result = sorted(result, key=lambda row: 1/row['profit'])
        return result[0:max_number]

