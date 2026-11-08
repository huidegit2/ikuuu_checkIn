import requests, json, re, os, time
import hmac, hashlib, base64, urllib.parse

session = requests.session()

url = os.environ.get('URL')
login_url = '{}/auth/login'.format(url)
check_url = '{}/user/checkin'.format(url)
logout_url = '{}/user/logout'.format(url)

# 钉钉机器人：从 GitHub Actions Secrets 读取（加签模式）
DING_WEBHOOK = os.environ.get('DINGTALK_WEBHOOK', '').strip()
DING_SECRET = os.environ.get('DINGTALK_SECRET', '').strip()

header = {
        'origin': 'https://ikuuu.one',
        'user-agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36'
}


def send_dingtalk(content):
    if not DING_WEBHOOK:
        print('[钉钉] 未配置 DINGTALK_WEBHOOK，跳过通知')
        return
    webhook = DING_WEBHOOK
    if DING_SECRET:
        ts = str(round(time.time() * 1000))
        string_to_sign = '{}\n{}'.format(ts, DING_SECRET)
        sign = urllib.parse.quote_plus(base64.b64encode(
            hmac.new(DING_SECRET.encode(), string_to_sign.encode(), hashlib.sha256).digest()
        ))
        sep = '&' if '?' in webhook else '?'
        webhook = '{}{}timestamp={}&sign={}'.format(webhook, sep, ts, sign)
    payload = {'msgtype': 'text', 'text': {'content': 'ikuuu 签到通知\n' + content}}
    try:
        r = requests.post(webhook, json=payload, timeout=10)
        print('[钉钉] 推送结果:', r.status_code, r.text[:200])
    except Exception as e:
        print('[钉钉] 推送失败:', e)


def checkIn(email, passwd):
    masked = (email[:3] + '***') if email else '***'
    data = {'email': email, 'passwd': passwd}
    try:
        print('账户【' + masked + '】进行登录...')
        response = json.loads(session.post(url=login_url, headers=header, data=data).text)
        print(response['msg'])
        result = json.loads(session.post(url=check_url, headers=header).text)
        print(result['msg'])
        send_dingtalk('{}: {}'.format(masked, result['msg']))
        session.get(logout_url)
    except Exception as e:
        print('签到失败:', e)
        send_dingtalk('{}: 签到失败'.format(masked))
        session.get(logout_url)


if __name__ == '__main__':
    split = os.environ.get('INFO').split(',')
    for user in split:
        user_split = user.split('<split>')
        email = user_split[0]
        password = user_split[1]
        checkIn(email, password)
        time.sleep(2)
