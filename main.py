import requests, json, re, os, time
import hmac, hashlib, base64, urllib.parse

session = requests.session()

# 机场地址：优先用 URL secret；未配置时自动探测候选域名（ikuuu 会不定期换域名）
URL_CANDIDATES = [
    'https://ikuuu.pw',
    'https://ikuuu.one',
    'https://ikuuu.me',
    'https://ikuuu.art',
]

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36')

# 两种登录方式二选一：Cookie 直连（推荐）或邮箱密码登录
IKUUU_COOKIE = os.environ.get('IKUUU_COOKIE', '').strip()
INFO = os.environ.get('INFO', '').strip()

# 钉钉机器人：从 GitHub Actions Secrets 读取（加签模式）
DING_WEBHOOK = os.environ.get('DINGTALK_WEBHOOK', '').strip()
DING_SECRET = os.environ.get('DINGTALK_SECRET', '').strip()

url = ''


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


def base_headers(base):
    h = {
        'origin': base,
        'referer': base + '/user',
        'user-agent': UA,
        'x-requested-with': 'XMLHttpRequest',
        'accept': 'application/json, text/javascript, */*; q=0.01',
    }
    if IKUUU_COOKIE:
        h['Cookie'] = IKUUU_COOKIE
    return h


def detect_url():
    """用当前 Cookie 试探候选域名，返回第一个已登录可用的站点。"""
    print('[地址] 未配置 URL，开始自动探测...')
    for base in URL_CANDIDATES:
        try:
            r = requests.get(base + '/user', headers=base_headers(base),
                             timeout=12, allow_redirects=False)
            loc = r.headers.get('Location', '')
            if r.status_code == 200 and 'auth/login' not in loc and len(r.content) > 5000:
                print('[地址] 命中:', base)
                return base
            print('[地址]', base, '->', r.status_code, loc or '未登录/不可用')
        except Exception as e:
            print('[地址]', base, '不可达:', type(e).__name__)
    return None


def parse_result(r):
    """把签到响应统一转成可读文本。"""
    try:
        data = r.json()
        if isinstance(data, dict):
            return str(data.get('msg') or data.get('message') or data)
    except Exception:
        pass
    text = (r.text or '').strip()
    if 'auth/login' in r.url or '<form' in text and 'login' in text.lower():
        return 'Cookie 已失效（被重定向到登录页），请重新抓一次 Cookie'
    return (text[:200] or 'HTTP {}（无响应内容）'.format(r.status_code))


def checkin_with_cookie(masked):
    """Cookie 模式：跳过登录，直接带 Cookie 请求签到接口。"""
    r = session.post(url + '/user/checkin', headers=base_headers(url), timeout=20)
    msg = parse_result(r)
    print('[签到]', msg)
    send_dingtalk('{}: {}'.format(masked, msg))
    return msg


def checkin_with_password(email, passwd):
    """兼容原模式：邮箱密码登录后签到。"""
    masked = (email[:3] + '***') if email else '***'
    try:
        print('账户【' + masked + '】进行登录...')
        resp = session.post(url + '/auth/login', headers=base_headers(url),
                            data={'email': email, 'passwd': passwd}, timeout=20)
        print('[登录]', parse_result(resp))
        r = session.post(url + '/user/checkin', headers=base_headers(url), timeout=20)
        msg = parse_result(r)
        print('[签到]', msg)
        send_dingtalk('{}: {}'.format(masked, msg))
    except Exception as e:
        print('签到失败:', e)
        send_dingtalk('{}: 签到失败：{}'.format(masked, e))


if __name__ == '__main__':
    try:
        url = (os.environ.get('URL') or '').strip().rstrip('/')
        if url:
            print('[地址] 使用配置的 URL:', url)
        else:
            url = detect_url()
            if not url:
                raise ValueError('所有候选域名均不可用，请手动配置 URL secret（机场地址）')

        if IKUUU_COOKIE:
            m = re.search(r'email=([^;]+)', IKUUU_COOKIE)
            email = urllib.parse.unquote(m.group(1)) if m else ''
            masked = (email[:3] + '***') if email else 'Cookie账号'
            print('[模式] Cookie 直连签到，账号:', masked)
            checkin_with_cookie(masked)
        elif INFO:
            print('[模式] 邮箱密码登录')
            for user in INFO.split(','):
                parts = user.split('<split>')
                if len(parts) < 2 or not parts[0].strip():
                    raise ValueError('INFO 格式错误：' + user[:30])
                checkin_with_password(parts[0].strip(), parts[1].strip())
                time.sleep(2)
        else:
            raise ValueError('既未配置 IKUUU_COOKIE，也未配置 INFO，无法签到')
    except Exception as e:
        print('签到任务异常:', e)
        send_dingtalk('签到任务异常：{}'.format(e))
        raise
