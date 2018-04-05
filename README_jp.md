# cryptowelder
[![Build Status][travis-icon]][travis-page] [![Coverage Status][coverall-icon]][coverall-page]

[travis-page]:https://travis-ci.org/after-the-sunrise/cryptowelder
[travis-icon]:https://travis-ci.org/after-the-sunrise/cryptowelder.svg?branch=master
[coverall-page]:https://coveralls.io/github/after-the-sunrise/cryptowelder?branch=master
[coverall-icon]:https://coveralls.io/repos/github/after-the-sunrise/cryptowelder/badge.svg?branch=master

* :us: [English](./README.md)
* :jp: [日本語](./README_jp.md)

## 概要

**Cryptowelder**は、暗号通貨の時価・口座残高・ポジション・取引高・損益などの取引状況を可視化するためのアプリケーションです。

![Grafanaダッシュボード画面](./docs/img/dashboard.png)


## 機能紹介

### :zap: 時系列データの可視化
様々な時系列データを収集し、グラフや表などで表示。
* 市場価格
* 口座残高・証拠金
* 信用ポジション・未実現損益
* 日次・月次の取引損益
* 過去N日間の取引金額

### :zap: カスタマイズ可能なWeb画面・通知
デスクトップマシンあるいはモバイル端末の標準ウェブブラウザーから取引状況を確認。

画面に表示されるデータはリアルタイムで更新され、当日・過去24時間・今週・過去N日間・任意の時間T1〜T2など、
表示対象とする時間範囲を切り替えることができます。

グラフや表などの部品は、ウェブ画面上からドラッグ＆ドロップで追加可能です。それぞれの部品を画面内の表示したい位置へ配置し、
独自のレイアウトやダッシュボードを構築することができます。

また、それぞれの部品に対して、任意の通知条件を設定することも可能です。
（例：「数値Xが値Yとなった場合、[Slack](https://slack.com/)へ通知」）

### :zap: 複数通貨・複数取引所の統一評価
複数の通貨・取引所のデータを収集・保存し、同一の画面内に表示することによって、通貨間・取引所間で比較・分析。

また、様々な通貨建て（例：JPY, USD, BTC, ETH, ...）で提示されている価格は、すべて単一のホーム通貨（例：JPY）へ
換算して表示することができます。どの通貨をホーム通貨とするか、どの換算レートを利用して通貨換算を行うかなどの評価設定は動的に変更可能です。

### :zap: API Access
収集した時系列データは、特別な復号化を必要とせずに、標準のSQL (例：[JDBC](https://jdbc.postgresql.org/)、
[ODBC](https://odbc.postgresql.org/))で直接取得可能。

[Prometheus Client](https://github.com/prometheus/client_python)が標準で組み込まれているため、
HTTPを利用したテキスト形式でも取得可能です。

[Grafana HTTP API](http://docs.grafana.org/http_api/)を利用し、ダッシュボードや通知の管理もできます。


## 使い方

### 仕組み
このアプリケーションは、下記の組み合わせで構成されています：
* 時系列データをパブリック・プライベートAPIから収集するための[Python](https://www.python.org/)スクリプト
* 収集した時系列データを保存するための関係データベース ([PostgreSQL](https://www.postgresql.org/))
* 時系列データを可視化および通知を行うための[Grafana](https://grafana.com/)

### システム要件
* Linuxマシン、コマンドライン操作およびインターネットへの直接続。 推薦要件：
    * クラウド上の仮想マシン、およびSSH経由でのアクセス(例：[AWS](https://aws.amazon.com/ec2/), [Azure](https://azure.microsoft.com/en-us/services/virtual-machines/), [GCE](https://cloud.google.com/compute/?hl=ja))
    * 近代的なLinuxオペレーティングシステム(例：[CentOS](https://www.centos.org/) 7.x x64)
    * 2GB以上のメモリ
    * 50GB以上のディスクスペース（SSDが望ましい）
* Python 3.x以上とpip（`pyenv` + `pyenv-virtualenv`推薦）
* PostgreSQL 10.x以上 
* Grafana 5.x以上
* 各取引所のプライベートAPIへアクセスするためのトークン 
* 各アプリケーションをインストールするための、Linuxの基本的な知識・作業経験
* 各アプリケーションの設定変更およびカスタマイズするための、Python・SQLの基本的な知識・作業経験 

### インストール手順
1. PostgreSQLデータベースのインストールおよび設定
    1. データベース`cryptowelder`を`UTC`のタイムゾーンで新規作成
    2. [DDL](./etc/DDL.sql)スクリプトと[DML](./etc/DML.sql)スクリプトとを実行
    3. データベースユーザ`grafana`を新規作成、読み取り権限を付与
2. Pythonスクリプトの設定および起動
    1. pipで依存ライブラリを取得　(`pip install -r requirements.txt`)
    2. アクセストークンや収集設定を記述したローカルの設定ファイル(`~/.cryptowelder`)を配置
    3. スクリプト(`sh cryptowelder.sh`)を起動し、データの収集とデータベースへの保存とを開始 
3. Grafanaのインストールおよび起動
    1. Grafanaユーザのセキュリティ権限を設定 ([localhost:3000](http://localhost:3000))
    2. [構築済みのテンプレート](./etc/GRAFANA.json)をインポート

### 安全の確保
通常、複数のセキュリティポリシーが標準で有効となっているため、インターネットから直接Grafanaへアクセスできないことがあります。

簡便的な回避手段として[SSHトンネリング](https://en.wikipedia.org/wiki/Tunneling_protocol#Secure_Shell_tunneling)を利用する方法があります。
```
ssh -L 3000:localhost:3000 cryptowelder@my-virtual-machine
```

SSHトンネリングを使用せずにインターネットからの直接アクセスを許可するには、少なくとも下記の設定を行うことをお勧めします。  
* ルートでのログインを禁止、およびSSHのパスワード認証禁止（公開鍵認証のみ許可）
* Grafanaの待ち受けポートに対して接続を許可するファイアウォール設定、およびGrafanaのバインドアドレスを`localhost`から`0.0.0.0`（あるいは特定のIF）へと変更
* カスタムドメインの購入 (cf: [Google Domain](https://domains.google/))、SSL証明書の取得(cf: [Let’s Encrypt](https://letsencrypt.org/))、およびGrafanaの通信プロトコルを`HTTP`から`HTTPS`へ変更

※　**これらの設定が全てではありません。**一般的なサーバーセキュリティに詳しくない場合、担当のシステム管理者へ相談してください。


## 免責条項
[ライセンス](./LICENSE)に従い、自己責任での利用となります。
作者では個別のセットアップおよび問い合わせ対応などを行う予定はありません。
