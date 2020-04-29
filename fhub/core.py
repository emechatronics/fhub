#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2020 Antonio Rodríguez García
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

from datetime import datetime
from time import sleep as _sleep

import pandas as pd
import requests

from .utils import FinnhubError
from .utils import _json_to_df_candle, _rename_quote, _check_resolution
from .utils import _to_dataframe, _check_kind, _recursive
from .utils import _unixtime


class Session:
    BASE_URL = 'https://finnhub.io/api/v1/'
    AVAILABLE_METRICS = [
        'price',
        'valuation',
        'growth',
        'margin',
        'management',
        'financialStrength',
        'perShare'
    ]
    """
    Finnhub API client.  You need a valid API key from Finnhub.
    """

    def __init__(
            self,
            key,
            verbose=False
    ):
        self.key = key
        self.verbose = verbose
        self.session = self._init__session()

    @staticmethod
    def _init__session():
        session = requests.session()
        session.headers.update({'Accept': 'application/json',
                                'User-Agent': 'finnhub/api'})
        return session

    def _request(self,
                 endpoint,
                 params=None):
        if params is None:
            params = {'token': self.key}
        else:
            params.update({'token': self.key})
        r = self.session.get(
            f"{self.BASE_URL}{endpoint}",
            params=params
        )
        if self.verbose:
            print(r.url)
            print(r.status_code)
            print(r.content)
        if r.ok:
            return r.json()
        else:
            raise FinnhubError(r.content.decode("utf-8"))

    @_check_kind
    @_to_dataframe()
    def exchanges(self,
                  kind='stock'):
        """
        List supported exchanges.
        :param kind: Kind of exchanges, default stock. Available: stock, forex, crypto.
        :return: dataframe with name, code and currency of exchanges.
        """
        _endpoint = f"{kind}/exchange"
        return self._request(_endpoint)

    @_check_kind
    @_to_dataframe()
    def symbols(self,
                exchange,
                kind='stock'):
        _endpoint = f"{kind}/symbol"
        params = {
            'exchange': exchange
        }
        return self._request(_endpoint, params)

    @_to_dataframe()
    def news(self,
             category='general',
             minid=0):
        _endpoint = 'news'
        params = {
            'category': category,
            'minId': minid
        }
        return self._request(_endpoint, params)

    @_to_dataframe()
    def company_news(
            self,
            symbol
    ):
        _endpoint = f"news/{symbol}"
        return self._request(_endpoint)

    @_to_dataframe()
    def profile(
            self,
            symbol=None,
            isin=None,
            cusip=None
    ):
        _ticker = {
            'symbol': symbol,
            'isin': isin,
            'cusip': cusip
        }

        if not any(_ticker.values()):
            print('You must pass one of symbol, isin or cusip')
            return

        params = {k: v for k, v in _ticker.items() if v}
        if len(params) > 1:
            print('You must pass only one of symbol, isin or cusip')
            return

        _endpoint = f"news/profile"
        return self._request(_endpoint, params)

    @_recursive
    def metrics(
            self,
            symbol,
            metric='margin'
    ):

        _endpoint = 'stock/metric'
        params = {
            'symbol': symbol,
            'metric': metric
        }
        _json = self._request(
            _endpoint,
            params
        )
        _df = pd.DataFrame.from_dict(_json['metric'], orient='index')
        _df.columns = [_json['symbol']]
        return _df

    @_recursive
    def all_metrics(
            self,
            symbol
    ):
        _metrics = {}
        for _metric in self.AVAILABLE_METRICS:
            _metrics[_metric] = self.metrics(symbol, _metric)
            _sleep(0.1)
        return pd.concat(_metrics)

    def investor_ownership(
            self,
            symbol,
            limit=None
    ):
        _endpoint = 'stock/investor-ownership'
        params = {'symbol': symbol}
        if limit is not None:
            params.update({'limit': limit})
        _json = self._request(
            _endpoint,
            params
        )
        _df = pd.json_normalize(
            _json,
            record_path='ownership',
            meta='symbol',
        )
        return _df

    def fund_ownership(
            self,
            symbol,
            limit=None
    ):
        _endpoint = 'stock/fund-ownership'
        params = {'symbol': symbol}
        if limit is not None:
            params.update({'limit': limit})
        _json = self._request(
            _endpoint,
            params
        )
        _df = pd.json_normalize(
            _json,
            record_path='ownership',
            meta='symbol',
        )
        return _df

    def ownership(
            self,
            symbol
    ):
        _invs = self.investor_ownership(symbol)
        _funds = self.fund_ownership(symbol)
        _invs['kind'] = 'INVESTOR'
        _funds['kind'] = 'FUND'
        return pd.concat([_invs, _funds])

    def executive(
            self,
            symbol
    ):
        _endpoint = 'stock/executive'
        params = {'symbol': symbol}

        _json = self._request(
            _endpoint,
            params
        )
        return pd.json_normalize(
            _json,
            record_path='executive',
            meta='symbol',
        )

    @_recursive
    def sentiment(
            self,
            symbol
    ):
        _endpoint = 'news-sentiment'
        params = {'symbol': symbol}

        _json = self._request(
            _endpoint,
            params
        )
        return pd.json_normalize(_json).T.rename(
            columns={0: _json['symbol']}
        )

    @_recursive
    def peers(
            self,
            symbol
    ):
        """
        Get company peers. Return a list of peers in the same country and GICS sub-industry
        :param symbol: symbol of the company
        :return: list of peers symbols
        """
        _endpoint = 'stock/peers'
        params = {'symbol': symbol}

        return self._request(
            _endpoint,
            params
        )

    @_recursive
    def upgrade_downgrade(
            self,
            symbol
    ):
        """
        Get latest stock upgrade and downgrade
        :param symbol: symbol of the company
        :return: dataframe with latest stock upgrades/downgrades
        """
        _endpoint = 'stock/upgrade-downgrade'
        params = {'symbol': symbol}
        _json = self._request(
            _endpoint,
            params
        )
        _df = pd.DataFrame(_json)
        _df['gradeTime'] = pd.to_datetime(_df['gradeTime'], unit='s')
        return _df

    @_recursive
    def recommendation(
            self,
            symbol
    ):
        """
        Get latest analyst recommendation trends for a company.
        :param symbol: symbol of the company
        :return: dataframe with recommendations
        """
        _endpoint = 'stock/recommendation'
        params = {'symbol': symbol}

        _df = pd.DataFrame(self._request(
            _endpoint,
            params
        ))

        _df['period'] = pd.to_datetime(_df['period'])
        return _df.set_index('period')[['strongBuy', 'buy', 'hold', 'sell', 'strongSell']]

    @_recursive
    @_to_dataframe('serie')
    def price_target(
            self,
            symbol
    ):
        """
        Get latest price target consdf = pd.DataFrame(ensus.
        :param symbol: symbol of the company
        :return: dataframe with recommendations
        """
        _endpoint = 'stock/price-target'
        params = {'symbol': symbol}

        return self._request(
            _endpoint,
            params
        )

    @_to_dataframe()
    def economic_code(self):
        _endpoint = "economic/code"
        return self._request(_endpoint)

    def economic(
            self,
            economic_code,
            get_unit=False
    ):
        _endpoint = "economic"
        params = {
            'code': economic_code
        }

        _json = self._request(
            _endpoint,
            params
        )
        _df = pd.DataFrame(_json)
        _codes = self.economic_code()
        _unit = 'value'
        if get_unit:
            _unit = _codes.set_index('code').loc[economic_code, 'unit']
        _df.columns = ['date', _unit]
        _df = _df.set_index('date')
        _df.index = pd.to_datetime(_df.index)
        return _df

    @_recursive
    @_to_dataframe(_type='serie')
    def quote(
            self,
            symbol
    ):
        _endpoint = 'quote'
        params = {'symbol': symbol}

        return _rename_quote(
            self._request(
                _endpoint,
                params
            )
        )

    @_recursive
    @_check_kind
    def candle(
            self,
            symbol,
            kind='stock',
            start=None,
            end=None,
            resolution='D',
            adjusted=True
    ):
        if not _check_resolution(resolution):
            return
        adjusted = 'true' if adjusted else 'false'
        if end is None:
            end = datetime.now().strftime("%Y-%m-%d")
        if start is None:
            start = '2000-01-01'

        params = {
            'symbol': symbol,
            'resolution': resolution,
            'from': _unixtime(start),
            'to': _unixtime(end)
        }

        if kind == 'stock':
            params.update({'adjusted': adjusted})
        _endpoint = f'{kind}/candle'
        _json = self._request(
            _endpoint,
            params
        )
        if self.verbose:
            print(_json)
        if _json is None:
            return None
        else:
            if _json['s'] == 'no_data':
                print(f"{params['symbol']} :  Data no available.")
                return None
            else:
                df = _json_to_df_candle(_json)
                return df
