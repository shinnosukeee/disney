# coding:utf-8
from selenium import webdriver
from selenium.webdriver.support.ui import Select
from time import sleep
import requests, os, datetime, yaml, warnings, calendar, ssl
from smtplib import SMTP, SMTP_SSL
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from pywebio.input import select, radio, input_group
from pywebio.output import put_html, put_table, popup, put_markdown, put_buttons, close_popup
from datetime import datetime, timedelta
from pynotificator import DesktopNotification

warnings.simplefilter('ignore')

# カレンダーの作成
def get_date_list():
    dt_now = datetime.now()
    year = dt_now.year
    month = dt_now.month
    day = dt_now.day
    date_list = [datetime(year, month, day) + timedelta(days=i) for i in range(calendar.monthrange(year, month)[1])]
    date_str_list = [d.strftime("%Y/%m/%d") for d in date_list]
    return date_str_list

# レストランのリスト作成
def get_restaurant_name():
    with open("restaurant.txt", "r", encoding='utf8') as a:
        restaurant_name = []
        dict_restaurant = {}
        for line in a:
            restaurant_name.append(line.rstrip().rsplit(" ")[1])
            dict_restaurant[line.rstrip().rsplit(" ")[1]] = line.rstrip().rsplit(" ")[0]
    return restaurant_name, dict_restaurant

# 入力フォーム
def input_form(restaurant_list):
    adult_list = list(range(1, 11))
    result = input_group("TDRモニタリング", [
        select('レストラン', restaurant_list, name="restaurant"),
        select('人数', adult_list, name="adult"),
        select('インパ予定日', get_date_list(), name="date"),
        radio("インターバル", options=["1分", "5分", "10分"], inline=True, name="interval"),
    ])
    return result

# 入力エラーの場合のポップアップ
def show_popup():
    popup('入力に不備があります', [
        put_markdown('**インターバル**を選択してください'),
        put_buttons(['Close'], onclick=lambda _: close_popup())
    ])

# モニタリング開始確認
def output(result, dict_restaurant):
    put_html('<h1>以下の内容でモニタリングを開始しました<br>予約空きが見つかればメールでお知らせします</h1>')
    put_table([
        ["レストラン", result["restaurant"]],
        ["人数", str(result["adult"]) + "人"],
        ["インパ予定日", result["date"]],
        ["インターバル", result["interval"]],
    ])
    # YAMLファイルへ書き込む
    with open("config.yaml", "w", encoding='utf8') as yf:
        yaml.dump(result, yf, allow_unicode=True, default_flow_style=False)

# フォームの入力から実行開始まで
def form():
    while True:
        restaurant_list, dict_restaurant = get_restaurant_name()
        result = input_form(restaurant_list)
        print(result)
        if result["interval"] is None:
            show_popup()
        else:
            break
    output(result, dict_restaurant)
    dn = DesktopNotification('のモニタリングを開始しました', title='TDRモニタリング', subtitle=result["restaurant"])
    dn.notify()

# 設定ファイルの読み込み
def read_config():
    with open('config.yaml', 'r', encoding='utf8') as yml:
        config = yaml.safe_load(yml)
        print(config)
        return config

# レストランの辞書型を作成
def read_restaurant():
    dict_restaurant = {}
    with open("restaurant.txt", "r", encoding='utf8') as a:
        for i in a:
            i = i.rstrip()
            num = i.split(" ")[0]
            name = i.split(" ")[1]
            dict_restaurant[name] = num
    return dict_restaurant

# メール送信機能の追加
def create_mail_message_mime(from_email, to_email, message, subject, filepath=None, filename=""):
    # MIMETextを作成
    msg = MIMEMultipart()
    msg['Subject'] = subject
    msg['From'] = from_email
    msg['To'] = to_email
    msg.attach(MIMEText(message, 'plain', 'utf-8'))

    # 添付ファイルの設定
    if filepath:
        path = filepath
        with open(path, 'r') as fp:
            attach_file = MIMEText(fp.read(), 'plain')
            attach_file.add_header(
                "Content-Disposition",
                "attachment",
                filename=filename
            )
            msg.attach(attach_file)
    return msg

def send_email(msg, account, password, host='smtp.example.com', port=465):
    context = ssl.create_default_context()
    server = SMTP_SSL(host, port, context=context)
    server.login(account, password)
    server.send_message(msg)
    server.quit()

# メール通知
def send_mail(notification_message):
    from_email = ""
    to_email = ""
    subject = "TDR予約空き通知"
    message = notification_message
    account = ""
    password = ""
    host = ""
    port = 465

    mime = create_mail_message_mime(from_email, to_email, message, subject)
    send_email(mime, account, password, host, port)

# ブラウザ操作部分
def chrome(config, dict_restaurant):
    # ChromeDriverの起動
    options = Options()
    options.add_argument("--headless")  # 画面を表示しない
    options.add_argument("--disable-gpu")  # GPUを無効化
    options.add_argument("--no-sandbox")  # サンドボックス機能を無効化
    options.add_argument("--disable-dev-shm-usage")  # /dev/shm を無効化（Linux 系の問題回避）
    options.add_argument("--remote-debugging-port=9222")  # デバッグ用ポートを開く
    options.add_argument("--window-size=1920,1080")  # ウィンドウサイズを指定
    service = Service(executable_path='chromedriver.exe')  # ChromeDriver
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(60)  # タイムアウトを60秒に設定
    driver.implicitly_wait(10)

    try:
        # 予約トップページへ遷移
        driver.get("https://reserve.tokyodisneyresort.jp/top/")
        sleep(3)

        # "レストラン"のイメージリンクをクリック
        driver.find_element("xpath", "//img[@src='/cgp/images/jp/pc/btn/btn_gn_04.png']").click()
        sleep(3)

        # 同意書の同意ボタンをクリック
        driver.find_element("xpath", "//img[@src='/cgp/images/jp/pc/btn/btn_close_08.png']").click()
        driver.implicitly_wait(3)

        # 日付の指定
        driver.find_element("id", 'searchUseDateDisp').send_keys(config["date"])

        # 人数の指定
        color_element = driver.find_element("id", 'searchAdultNum')
        color_select_element = Select(color_element)
        color_select_element.select_by_value(str(config["adult"]))

        # レストランの指定
        color_element = driver.find_element("id", 'nameCd')
        color_select_element = Select(color_element)
        color_select_element.select_by_value(dict_restaurant[config["restaurant"]])

        # "検索する"をクリック
        driver.find_element("xpath", "//input[@src='/cgp/images/jp/pc/btn/btn_search_01.png']").click()
        sleep(1)

        # ページのスクロール
        height = driver.execute_script("return document.body.scrollHeight")
        for x in range(1, height):
            driver.execute_script("window.scrollTo(0, " + str(x) + ");")
        sleep(3)

        # 検索結果から空き状況を判定
        if "お探しの条件で、空きはございません。" in driver.find_element("id", 'hasNotResultDiv').text:
            print(driver.find_element("id", 'hasNotResultDiv').text)
        else:
            print("空きが見つかりました")
            send_mail('空きが出ました\n')

    finally:
        driver.quit()

########### main ############
form() # 入力フォーム
while True:
    config = read_config() # 設定ファイルの読み込み
    dict_restaurant = read_restaurant() # レストランの辞書作成
    chrome(config, dict_restaurant) # ブラウザの操作
    sleep(int(config["interval"].replace("分", "")) * 60) # 一定時間スリープ

#レストランのリスト
#RESC0 イーストサイド･カフェ
#RGAW0 グレートアメリカン・ワッフルカンパニー
#RCSC0 センターストリート ･ コーヒーハウス
#RJRH0 れすとらん北齋
#RCPR0 クリスタルパレス・レストラン
#RBBY0 ブルーバイユー・レストラン
#RPLT2 ポリネシアンテラス・レストラン
#RDHS2 ザ・ダイヤモンドホースシュー
#RLTG0 ラ・タベルヌ・ド・ガストン
#RBPP0 ビッグポップ
#RMGL0 マゼランズ
#RRDC0 リストランテ・ディ・カナレット
#RSSD0 Ｓ.Ｓ.コロンビア･ダイニングルーム
#RTRL1 テディ・ルーズヴェルト・ラウンジ
#RJRS0 レストラン櫻
#RHZB1 ホライズンベイ・レストラン
# RCHM0 シェフ・ミッキー
# REPG0 エンパイア・グリル
# RHPL3 ハイピリオン・ラウンジ「期間限定ケーキセット」
# RHPL5 ハイピリオン・ラウンジ 「ディズニー ツイステッドワンダーランド」スペシャルケーキセット
# RHPL4 ハイピリオン・ラウンジ「プレミアムスイーツセット」
# RTIC3 チックタック・ダイナー　ブレッドセレクション
# RTIC2 チックタック・ダイナー　スペシャルブレッド
# ROCE0 オチェーアノ／ブッフェ
# ROCE1 オチェーアノ／コース
# RSRG0 シルクロードガーデン
# RBVL0 ベッラヴィスタ・ラウンジ
# RBVL1 ベッラヴィスタ・ラウンジ／後方席（窓側から3～4列目）
# RSWG0 シャーウッドガーデン・レストラン
# RCAN0 カンナ
# RDML2 ドリーマーズ・ラウンジ（アフタヌーンティーセット限定)
# RDML4 ドリーマーズ・ラウンジ（パスタセット限定)
