from google.cloud import storage
from google.auth.exceptions import RefreshError
import os
import io
import numpy as np
import pandas as pd
import audioop
import time
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from google.cloud import speech

import re

import streamlit as st
from audio_recorder_streamlit import audio_recorder

##gmail用
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.message import EmailMessage
from email import encoders
import base64
import mimetypes


os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'tech0-step3-te-bd23bed77076.json'

def upload_blob_from_memory(bucket_name, contents, destination_blob_name):
    #Google cloud storageへ音声データ（Binaly）をUploadする関数
    
    #Google Cloud storageの　バケット（like フォルダ）と作成するオブジェクト（like ファイル）を指定する。
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)

    #録音データをステレオからモノラルに変換
    contents = audioop.tomono(contents, 1, 0, 1)
    
    #指定したバケット、オブジェクトにUpload
    blob.upload_from_string(contents)

    return contents


def transcript(gcs_uri):
    #Speech to textに音声データを受け渡して文字起こしデータを受け取る関数
    
    audio = speech.RecognitionAudio(uri=gcs_uri)
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=48000,
        language_code="ja-JP",
    )

    operation = speech.SpeechClient().long_running_recognize(config=config, audio=audio)
    response = operation.result(timeout=90)
   
    transcript = []
    for result in response.results:
        transcript.append(result.alternatives[0].transcript)
        
    return transcript

def recorder():
    contents = audio_recorder(
        energy_threshold = (1000000000,0.0000000002), 
        pause_threshold=0.1, 
        sample_rate = 48_000,
        # text="Clickして録音開始　→　"
        text="Clickして録音開始　→　"
    )

    return contents

def countdown():
    ph = st.empty()
    N = 60*5
    #修正　「Skipして回答」→「回答に移る」
    # exit = st.button("Skipして回答")
    exit = st.button("回答に移る")
    

    for secs in range(N,0,-1):
        mm, ss = secs//60, secs%60
        ph.metric("検討時間", f"{mm:02d}:{ss:02d}")

        time.sleep(1)
        
        if secs == 0:
            return 2

        if exit:
            return 2

def countdown_answer():
    ph = st.empty()
    N = 60*5

    for secs in range(N,0,-1):
        mm, ss = secs//60, secs%60
        ph.metric("回答時間", f"{mm:02d}:{ss:02d}")

        time.sleep(1)
        if secs == 1:
            text_timeout = "時間切れです。リロードして再挑戦してください  \n※注意※　timeout前に録音を完了していた場合はそのまま少々お待ちください"
            return text_timeout

def google_spread_CAL(list):
    scope = ['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/drive']
    json = 'tech0-step3-te-bd23bed77076.json'

    credentials = ServiceAccountCredentials.from_json_keyfile_name(json, scope)
    gc = gspread.authorize(credentials)

    SPREADSHEET_KEY = '1eXLTugi8tzy_L_keNkeu-Slyl6YbHlRJ7-WDXdNP7n4'
    # worksheet = gc.open_by_key(SPREADSHEET_KEY).sheet1
    worksheet = gc.open_by_key(SPREADSHEET_KEY).worksheet('ClientAnswerList')

    items = list

    worksheet.append_row(items)

def google_spread_QL():
    scope = ['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/drive']
    json = 'tech0-step3-te-bd23bed77076.json'

    credentials = ServiceAccountCredentials.from_json_keyfile_name(json, scope)
    gc = gspread.authorize(credentials)

    SPREADSHEET_KEY = '1eXLTugi8tzy_L_keNkeu-Slyl6YbHlRJ7-WDXdNP7n4'
    worksheet = gc.open_by_key(SPREADSHEET_KEY).worksheet('QuestionList')

    data = worksheet.get_all_values()
    headers = data.pop(0)  # タイトル行を取り出す
    data.pop(0)  # 1行目（タイトル行）を除外する

    df_list = pd.DataFrame(data, columns=headers)

    return df_list

def message_base64_encode(message):
    return base64.urlsafe_b64encode(message.as_bytes()).decode()

def gmail(email):
    scopes = ['https://mail.google.com/']
    creds = Credentials.from_authorized_user_file('token.json', scopes)
    service = build('gmail', 'v1', credentials=creds)

    message = EmailMessage()
  
    message['To'] = email
    message['From'] = 'menstsu.quest.hagukumi@gmail.com'
    message['Subject'] = '面接クエスト 決済URLの送付（テスト）'
    message.set_content('この度は面接クエストをご利用いただきありがとうございます。  \n下記URLより決済を完了させてください。決済確認後にFeedback Sheetを作成させていただきます。 \nhttps://buy.stripe.com/test_14k28W8L71FH4PS28b')

    raw = {'raw': message_base64_encode(message)}
    service.users().messages().send(
        userId='me',
        body=raw
    ).execute()

# 有効なメールアドレスであるかを判定
def is_valid_email(email):
    email_regex = r'^\w+([\.-]?\w+)*@\w+([\.-]?\w+)*(\.\w{2,3})+$'
    return re.match(email_regex, email) is not None


st.title('ケース面接Quest')
st.info('パソコンおよび安定した通信環境での実施を推奨します')
st.write('ケース面接の練習ができるアプリです。')
st.text("<利用手順> \n① 「さっそくTry!」ボタンを押してください　\n② 練習したいファーム種別と問題を選択して「検討を開始する」ボタンを押してください  \n③ 5分間の検討時間の後、回答（音声録音）に移行します  \n④ 録音アイコンをクリックして回答を録音してください　\n⑤ Feedbackを希望する場合、「Feedbackを希望する」を選択して「Submit」ボタンを押してください  \n⑥ 入力されたメールアドレス宛に届く決済案内に沿って、決済を行ってください　\n⑦ 決済後5日以内に、現役コンサルタントのFeedbackをメールにて送付します！！")

if "state" not in st.session_state:
   st.session_state["state"] = 0

if "state_start" not in st.session_state:
   st.session_state["state_start"] = 0

if st.button("さっそくTry!"):
    st.session_state["state"] = 1

if st.session_state["state"] == 0:
    st.stop()

# 修正　リストを変更　question_listをインポート（※スプレッドに差し替えたい）
df_list = pd.read_csv("question_list.csv", header = 0)
# df_list = google_spread_QL()

# 初期表示を定義
initial = '--Please Select--'

# ファーム種別をセレクトボックスに表示
class_value = df_list['firm_class'].drop_duplicates().tolist()
option = initial
option = st.selectbox('練習したいファーム種別を選択してください', [initial] + class_value)

# 選択されたClassに対応するTitleの一覧を取得
title = initial
if option != initial:

    title_value = df_list[df_list['firm_class'] == option]['title'].tolist()
    # 採番を追加
    title_value = [f"{i+1:02d}：{title}" for i, title in enumerate(title_value)]
    # タイトルをセレクトボックスに表示
    title = st.selectbox('問題を選択してください', [initial] + title_value)
    title = title[3:]

# 選択されたTitleに対応するquestionを取得
if title != initial:
    question = ""
    question_value = df_list[df_list['title'] == title]['question'].tolist()
    if question_value:
        # question = st.success('■ 設問：' + question_value[0])
        st.write('■ 設問')
        question = st.success(question_value[0])
        # question = st.markdown(f"**■ 設問：**\n\n{question_value[0]}", unsafe_allow_html=True)

        if st.button('検討を開始する'):
                st.session_state["state_start"] = 1

# if question is not "":
#     st.success('■ 設問：　' + question)

#     if st.button('検討を開始する'):
#         st.session_state["state_start"] = 1

if st.session_state["state_start"] == 0:
    st.stop()

if st.session_state["state"] == 1:
    st.session_state["state"] = countdown()

contents = recorder()

if contents == None:
    st.info('①　アイコンボタンを押して回答録音　(アイコンが赤色で録音中)  \n②　もう一度押して回答終了　(再度アイコンが黒色になれば完了)')
    st.error('録音完了後は10秒程度お待ちください。')
    timeout_msg = countdown_answer()
    st.info(timeout_msg)
    st.stop()

st.audio(contents)

# 追加
st.info("再度アイコンボタンを押すと、録音のやり直しとなります。  \n先ほど録音したデータは削除されるためご注意ください。")

id = str(datetime.datetime.now()).replace('.','-').replace(' ','-').replace(':','-')
bucket_name = 'tech0-speachtotext'
destination_blob_name = 'test_' + id + '.wav'
gcs_uri="gs://" + bucket_name + '/' +destination_blob_name


with st.form("form1"):
    name = st.text_input("名前　※必須")
    email = st.text_input("メールアドレス　※必須")

    # 追加
    employment_type = st.radio(
        "サービスの利用目的　※必須",
        ("新卒面接対策", "中途面接対策（コンサル未経験者）", "中途面接対策（コンサル経験者）", "その他"),
    )

    # 「その他」の場合はテキスト入力させたいが、フォームの中だとうまく挙動しない・・・    
    if employment_type == "その他":
        other_employment_type = st.text_input("その他の利用目的を入力してください")
    else:
        other_employment_type = ""
    
    fb_request = st.radio(\
        "本提出の確認　※必須",
        ("現役コンサルタントからのFeedbackを希望する（2,000円／決済の案内に遷移します）", "Feedbackを希望しない（画面が終了します）")
        )
    if fb_request == "Feedbackを希望しない（画面が終了します）":
        fb_flag = "0"
    else:
        fb_flag = "1"

    #　追加
    # referrer_source = st.multiselect(
    #     "このサービスをどこで知りましたか？（複数回答可）　※任意",
    #     ("ブラウザ検索(Google等)","Twitter","Facebook","知人・友人経由","その他")
    # )
    st.markdown("このサービスをどこで知りましたか？（複数回答可）　※任意")
    source_options = ["ブラウザ検索(Google等)","Twitter","Facebook","知人・友人経由","その他"]
    source_responses = {}

    for option in source_options:
        checked = st.checkbox(option)
        if checked:
            source_responses[option] = 1
        else:
            source_responses[option] = 0

    interview_agreement = st.radio(
        "サービス内容の向上を目的としたインタビューを依頼した場合、ご協力いただくことは可能でしょうか？（Amazonギフト券500円をプレゼントいたします）※任意",
        ("はい","いいえ")
    )


    submit = st.form_submit_button("Submit")


try:

    if submit:

        ErrorFlg = 0

        if name == '':
            st.error('名前を入力してください')
            ErrorFlg = 1
        
        if email == '':
            st.error('メールアドレスを入力してください')
            ErrorFlg = 1
        
        if email != '':
            if not is_valid_email(email):
                st.error('無効なメールアドレスです。有効なメールアドレスを入力してください。')
                ErrorFlg = 1

        # 追加
        if employment_type == '':
            st.error('本サービスの利用目的を選択してください')
            ErrorFlg = 1

        # if other_employment_type == '':
        #     st.error('本サービスの利用目的を入力してください')

        # if (name != '' and email != '' and employment_type != ''):
        if ErrorFlg == 0:

            if fb_flag == "0":
                st.info('以上で終了です。')
                upload_blob_from_memory(bucket_name, contents, destination_blob_name)
                transcript = transcript(gcs_uri)
                text = '。\n'.join(transcript)
                # list = [id, name, email, title, text, gcs_uri, fb_flag]
                list = [id, name, email, employment_type, option, title, text, gcs_uri, source_responses["ブラウザ検索(Google等)"],source_responses["Twitter"],source_responses["Facebook"],source_responses["知人・友人経由"],source_responses["その他"], interview_agreement, fb_flag]
                google_spread_CAL(list)
                gmail(email)
                
            if fb_flag == "1":
                st.info('回答が提出されました。"12時間以内"に入力のメールアドレス宛に決済URLを送付します。')
                st.info('※注意※  \n決済が完了しなければ、Feedbackは送付されません。')
                st.info('※問い合わせ先※  \nmensetsu.quest.hagukumi@gmail.com')
                upload_blob_from_memory(bucket_name, contents, destination_blob_name)
                transcript = transcript(gcs_uri)
                text = '。\n'.join(transcript)
                # list = [id, name, email, question, text, gcs_uri, fb_flag]
                list = [id, name, email, employment_type, option, title, text, gcs_uri, source_responses["ブラウザ検索(Google等)"],source_responses["Twitter"],source_responses["Facebook"],source_responses["知人・友人経由"],source_responses["その他"], interview_agreement, fb_flag]
                google_spread_CAL(list)
                gmail(email)

except TypeError as e:
    print(f"エラーが発生しました: {e}")
    pass

except RefreshError as e:
    print(f"リフレッシュエラーが発生しました: {e}")
    # ここでエラー処理を行うか、passで無視するかを決定します
    pass

st.stop()