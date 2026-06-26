import os, threading, time as _t
from flask import Flask

# --- FLASK SERVER SETUP FOR RENDER (ADDED BY MINOX AUTO SETUP) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is successfully running on Render!"

def run_server():
    port = int(os.environ.get("PORT", 8080))
    try:
        app.run(host="0.0.0.0", port=port)
    except OSError:
        for fallback in [8081, 8082, 5050, 9000]:
            try:
                app.run(host="0.0.0.0", port=fallback)
                break
            except OSError:
                continue



import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import requests, json, time, uuid, re, csv, os, threading

# --- CONFIGURATION ---
TOKEN = "8602767691:AAENJ1IhhomX0EopfYUxEscMP69bLkiRvk8"  
ADMIN_ID = 5409553122
BOT_NAME = "𝐑𝐌-𝐗𝐄𝐋 𝐁𝐎𝐓"

# ============================================
# --- MULTI-PANEL CONFIGURATION ---
# ============================================
NEXA_API_KEY = "MRKVD1UFXWP"  # default fallback key

PANEL_DEFAULTS = {
    "active_panel": "voltx_sms",
    "voltx_sms_api_key": "MRKVD1UFXWP",
    "voltx_sms_base_url": "https://api.2oo9.cloud/MXS47FLFX0U/tnevs/@public/api",
    "stex_sms_api_key": "MWF1Z0QG1DJ",
    "stex_sms_base_url": "https://api.2oo9.cloud/MXS47FLFX0U/tness/@public/api",
    "zenex_api_key": "ZNX_IQ52ED851U09ZAZL062U26GL",
    "zenex_base_url": "https://api.zenexnetwork.com",
    "fastxotp_api_key": "MURAD_920E47039411AB1DD899DC2D",
    "fastxotp_base_url": "https://fastxotp.com",
}

PANEL_LABELS = {
    "voltx_sms": "⚡ VoltX SMS (2oo9)",
    "stex_sms":  "🔷 STEX SMS (2oo9)",
    "zenex":     "🌐 Zenex Network",
    "fastxotp":  "🚀 FastX OTP",
}

# ============================================
# --- ALLOWED SERVICES FILTER ---
# শুধু এই সার্ভিসগুলো দেখাবে (বাকি সব ফিল্টার হবে)
# ============================================
ALLOWED_APPS = {
    "facebook", "whatsapp", "telegram", "imo",
    "paypal", "tiktok", "discord", "indrive", "google"
}

def clean_base_url(url, panel):
    url = str(url).strip().rstrip('/')
    if panel == "zenex":
        url = re.sub(r'(/v1|/api|/api/v1)$', '', url)
    elif panel == "fastxotp":
        url = re.sub(r'(/api|/api/v1)$', '', url)
    return url.rstrip('/')

def get_api_credentials():
    data = load_data()
    panel_cfg = data.get("panel_config", PANEL_DEFAULTS)
    panel = panel_cfg.get("active_panel", "voltx_sms")
    if panel == "voltx_sms":
        key = panel_cfg.get("voltx_sms_api_key", PANEL_DEFAULTS["voltx_sms_api_key"])
        url = panel_cfg.get("voltx_sms_base_url", PANEL_DEFAULTS["voltx_sms_base_url"])
    elif panel == "stex_sms":
        key = panel_cfg.get("stex_sms_api_key", PANEL_DEFAULTS["stex_sms_api_key"])
        url = panel_cfg.get("stex_sms_base_url", PANEL_DEFAULTS["stex_sms_base_url"])
    elif panel == "zenex":
        key = panel_cfg.get("zenex_api_key", PANEL_DEFAULTS["zenex_api_key"])
        url = panel_cfg.get("zenex_base_url", PANEL_DEFAULTS["zenex_base_url"])
    elif panel == "fastxotp":
        key = panel_cfg.get("fastxotp_api_key", PANEL_DEFAULTS["fastxotp_api_key"])
        url = panel_cfg.get("fastxotp_base_url", PANEL_DEFAULTS["fastxotp_base_url"])
    else:
        key = PANEL_DEFAULTS["voltx_sms_api_key"]
        url = PANEL_DEFAULTS["voltx_sms_base_url"]
    return str(key).strip(), clean_base_url(url, panel), panel

def get_api_urls(panel, base_url):
    base_url = str(base_url).strip().rstrip('/')
    if panel == "zenex":
        return {
            "getnum":     f"{base_url}/v1/getnum",
            "otp":        f"{base_url}/v1/numsuccess/info",
            "balance":    f"{base_url}/v1/balance",
            "liveaccess": f"{base_url}/v1/active-ranges"
        }
    elif panel == "fastxotp":
        return {
            "getnum":     f"{base_url}/api/getnum",
            "otp":        f"{base_url}/api/otps",
            "balance":    f"{base_url}/api/balance",
            "liveaccess": f"{base_url}/liveaccess"
        }
    else:  # voltx_sms / stex_sms
        return {
            "getnum":     f"{base_url}/getnum",
            "otp":        f"{base_url}/success-otp",
            "balance":    f"{base_url}/balance",
            "liveaccess": f"{base_url}/liveaccess"
        }

def get_api_headers(panel, api_key):
    CT = "application/json"
    if panel == "zenex":
        return {"mapikey": api_key, "Content-Type": CT}
    elif panel == "fastxotp":
        return {"X-API-Key": api_key, "Content-Type": CT}
    else:  # voltx_sms / stex_sms
        return {"mauthapi": api_key, "Content-Type": CT}

# --- GLOBAL REUSABLE HTTP SESSION FOR ULTRA FAST API CALLS ---
http_session = requests.Session()

# ============================================
# --- LIVE RANGE CACHE (auto GET NUMBER) ---
# ============================================
_live_ranges_cache = {"data": None, "updated_at": 0}
_country_ranges_store = {}   # short_key -> range_string  (64-byte callback workaround)
_user_country_sessions = {}  # chat_id -> {"app": str, "countries": {idx: {"label":str,"ranges":[]}}} 

def get_clean_app_name(raw):
    """Normalize app/service name."""
    name = str(raw).strip()
    for prefix in ["sms_", "SMS_", "service_"]:
        if name.startswith(prefix):
            name = name[len(prefix):]
    return name.title()

def get_app_emoji_id_for_service(app_name):
    """Return emoji ID for a known app name."""
    lower = app_name.lower()
    mapping = {
        "instagram":       "emj_instagram",
        "facebook":        "emj_facebook",
        "tiktok":          "emj_tiktok",
        "telegram":        "emj_telegram",
        "whatsapp business": "emj_whatsapp_business",
        "whatsapp":        "emj_whatsapp",
        "twitter":         "emj_twitter",
        "discord":         "emj_discord",
        "google":          "emj_google",
        "apple":           "emj_apple",
        "microsoft":       "emj_microsoft",
        "teams":           "emj_teams",
        "snapchat":        "emj_snapchat",
        "uber":            "emj_uber",
        "amazon prime":    "emj_amazon_prime",
        "amazon":          "emj_amazon",
        "viber":           "emj_viber",
        "linkedin":        "emj_linkedin",
        "line":            "emj_line",
        "wechat":          "emj_wechat",
        "imo":             "emj_imo",
        "paypal":          "emj_paypal",
        "indrive":         "emj_indrive",
        "binance":         "emj_binance",
        "bybit":           "emj_bybit",
        "bkash":           "emj_bkash",
        "rocket":          "emj_rocket",
        "nagad":           "emj_nagad",
        "reddit":          "emj_reddit",
        "pinterest":       "emj_pinterest",
        "twitch":          "emj_twitch",
        "zoom":            "emj_zoom",
        "signal":          "emj_signal",
        "slack":           "emj_slack",
        "skype":           "emj_skype",
        "netflix":         "emj_netflix",
        "spotify":         "emj_spotify",
        "hoichoi":         "emj_hoichoi",
        "daraz":           "emj_daraz",
        "github":          "emj_github",
        "canva":           "emj_canva",
        "chatgpt":         "emj_chatgpt",
        "melbet":          "emj_melbet",
        "1xbet":           "emj_melbet",
    }
    for key, emoji_key in mapping.items():
        if key in lower:
            return get_emoji_id(emoji_key)
    return get_emoji_id("emj_number")

def fetch_live_ranges_by_app():
    """Fetch live ranges from API and group by app name. Returns dict or None."""
    global _live_ranges_cache
    now = time.time()
    # Cache valid for 5 minutes
    if _live_ranges_cache["data"] and (now - _live_ranges_cache["updated_at"]) < 300:
        return _live_ranges_cache["data"], None

    try:
        api_key, base_url, panel = get_api_credentials()
        api_urls = get_api_urls(panel, base_url)
        api_headers = get_api_headers(panel, api_key)
        url = api_urls.get("liveaccess", "")
        if not url:
            return None, "No liveaccess URL"

        r = http_session.get(url, headers=api_headers, timeout=15)
        if r.status_code != 200:
            return None, f"API error {r.status_code}"

        data = r.json()
        ranges_list = None

        if panel in ("voltx_sms", "stex_sms"):
            if isinstance(data, dict) and "data" in data:
                ranges_list = data["data"].get("services")
        elif panel == "fastxotp":
            if isinstance(data, dict):
                ranges_list = data.get("services") or data.get("data", {}).get("services")
        else:  # zenex
            if isinstance(data, dict):
                if "data" in data and isinstance(data["data"], dict):
                    ranges_list = data["data"].get("active_ranges")
                elif "active_ranges" in data:
                    ranges_list = data["active_ranges"]
            elif isinstance(data, list):
                ranges_list = data

        if not ranges_list:
            return None, "No ranges returned by API"

        top_by_app = {}

        if panel in ("voltx_sms", "stex_sms", "fastxotp"):
            for svc_obj in ranges_list:
                if not isinstance(svc_obj, dict): continue
                app = get_clean_app_name(svc_obj.get("sid", "Unknown"))
                rngs = svc_obj.get("ranges", [])
                if not app or not rngs: continue
                if app not in top_by_app:
                    top_by_app[app] = []
                top_by_app[app].extend(rngs)
        else:  # zenex
            for rng_obj in ranges_list:
                if not isinstance(rng_obj, dict): continue
                rng = rng_obj.get("range", "")
                app = get_clean_app_name(rng_obj.get("service", "Unknown"))
                if not rng or not app: continue
                if app not in top_by_app:
                    top_by_app[app] = []
                top_by_app[app].append(rng)

        # Sort by number of available ranges (descending)
        top_by_app = dict(sorted(top_by_app.items(), key=lambda x: len(x[1]), reverse=True))

        _live_ranges_cache["data"] = top_by_app
        _live_ranges_cache["updated_at"] = now
        return top_by_app, None

    except Exception as e:
        return None, str(e)

# --- SAFE JSON PARSER (handles empty / non-JSON API responses) ---
def safe_json_parse(resp):
    """Returns (data_dict_or_list, error_str_or_None)"""
    try:
        text = resp.text.strip() if resp.text else ""
        if not text:
            return None, f"Empty response (HTTP {resp.status_code})"
        data = resp.json()
        return data, None
    except Exception as e:
        snippet = (resp.text or "")[:300]
        return None, f"JSON Error (HTTP {resp.status_code}): {snippet}"

# --- ACTIVE NUMBER SESSIONS TRACKER ---
active_sessions = {}
active_sessions_lock = threading.Lock()

# --- PREMIUM CUSTOM EMOJIS ---
DEFAULT_CUSTOM_EMOJIS = {
    # --- Service App Emojis (Premium_App) ---
    "emj_telegram":          "5337010556253543833",
    "emj_instagram":         "5334868205091459431",
    "emj_facebook":          "5334807341109908955",
    "emj_tiktok":            "5339213256001102461",
    "emj_whatsapp":          "5334759662677957452",
    "emj_whatsapp_business": "5336814486701514414",
    "emj_bkash":             "5348469219761626211",
    "emj_rocket":            "5346042941196507141",
    "emj_binance":           "5348212415077064131",
    "emj_nagad":             "5352985330628730418",
    "emj_discord":           "5116246243646898866",
    "emj_imo":               "5337155807752524558",
    "emj_paypal":            "5776103539872896061",
    "emj_indrive":           "5298715455316303708",
    "emj_google":            "5335010201005231986",
    "emj_apple":             "5334637951894722661",
    "emj_microsoft":         "5334880948259427772",
    "emj_teams":             "5334590977837403844",
    "emj_snapchat":          "5359441366554255082",
    "emj_uber":              "5298715455316303708",
    "emj_amazon":            "4995019580536524226",
    "emj_viber":             "5463060437572528782",
    "emj_linkedin":          "6224222994265279792",
    "emj_line":              "5399818044866327279",
    "emj_wechat":            "5782757599560602950",
    "emj_twitter":           "5215726959056662534",
    "emj_reddit":            "4992421103847604984",
    "emj_pinterest":         "5346103513120258857",
    "emj_twitch":            "5233333563306301418",
    "emj_zoom":              "5881799193219043268",
    "emj_signal":            "5293998404404272267",
    "emj_slack":             "4994972469040251302",
    "emj_skype":             "4992613535562334989",
    "emj_netflix":           "6255738712664050133",
    "emj_spotify":           "5411392711146095115",
    "emj_amazon_prime":      "6111801057061374810",
    "emj_hoichoi":           "6104822598493801746",
    "emj_daraz":             "5336879280578138635",
    "emj_github":            "5417836094098007862",
    "emj_canva":             "5111661409008092227",
    "emj_chatgpt":           "5296516998996445955",
    "emj_bybit":             "5348372939479751825",
    "emj_melbet":            "5337102391244263212",

    # --- UI / Action Emojis (from premium sources) ---
    "emj_support":       "5334763399299506604",   # 💬 Support
    "emj_number":        "5861680977994060034",   # 📞 Number
    "emj_wallet":        "5190899075968441286",   # 💰 Balance (maskfix confirmed)
    "emj_profile":       "5382164415019768638",   # 👤 Profile
    "emj_refer":         "5420396762189831222",   # 🔗 Refer
    "emj_country":       "5355102594886833928",   # 🌐 Country/Live
    "emj_admin_panel":   "5350396951407895212",   # 👑 Admin
    "emj_ban":           "5420323339723881652",   # 🚫 Ban
    "emj_broadcast":     "5251671501702196837",   # 📢 Broadcast
    "emj_otp_coming":    "5386367538735104399",   # ⏳ Loading/OTP Coming
    "emj_otp_received":  "6237550015791765281",   # ⭐ OTP Received/Success
    "emj_message":       "5253742260054409879",   # ✉️ Message
    "emj_stop":          "5956074558044770726",   # 🛑 Stop
    "emj_successful":    "5859265295113261399",   # ✅ Successful
    "emj_changing":      "5267295703666824255",   # 🔄 Changing/Range
    "emj_add":           "5397916757333654639",   # ➕ Add
    "emj_link":          "5271604874419647061",   # 🔗 Link
    "emj_cross":         "5420130255174145507",   # ❌ Cross/Cancel
    "emj_gift":          "5970074171449808121",   # 🎁 Gift
    "emj_up":            "5244837092042750681",   # 📈 Up
    "emj_support_btn":   "5352888345972187597",   # 💬 Support Button
    "emj_key":           "5296369303661067030",   # 🔑 Key/OTP
    "emj_done":          "6298670698948724690",   # ✅ Done
    "emj_search":        "5839327279536149841",   # 🔍 Search
    "emj_share":         "5251671501702196837",   # 📢 Share
    "emj_otp_group":     "5253742260054409879",   # ✉️ OTP Group (msg - confirmed)
    "emj_renge_group":   "5355102594886833928",   # 🌐 Range Group (live - confirmed)
    "emj_gen_number":    "5370715282044100355",   # ⏳ Generate Number
    "emj_copy_link":     "5429483843541284898",   # 📋 Copy
}

# --- PREMIUM COUNTRY FLAGS (all 245 entries from Premium_Flag file) ---
PREMIUM_FLAGS = {
    "united states": "5913463998522592692",
    "ukraine": "5911406692007941050",
    "poland": "5913550391789752571",
    "kazakhstan": "5913724621433082323",
    "china": "5913779335021466780",
    "azerbaijan": "5911197578640233518",
    "european union": "5911106310585193018",
    "armenia": "5913272455866093666",
    "russian federation": "5913274246867456342",
    "russia": "5913274246867456342",
    "uzbekistan": "5911051846104912282",
    "germany": "5911096835887337583",
    "japan": "5913293711659241040",
    "turkey": "5910995113881901195",
    "belarus": "5911011185649521599",
    "united kingdom": "5913443365499703513",
    "uk": "5913443365499703513",
    "india": "5913754823643107921",
    "brazil": "5911148568768418614",
    "zambia": "5913564754160389778",
    "yemen": "5913346492512341993",
    "wales": "5911297801702084799",
    "vietnam": "5913428887164949581",
    "holy see (vatican city state)": "5911211932420938860",
    "vatican": "5911211932420938860",
    "vanuatu": "5913511535220625585",
    "uruguay": "5913623088406204470",
    "united arab emirates": "5913726554168365343",
    "uae": "5913726554168365343",
    "uganda": "5913488939397681980",
    "turkmenistan": "5913315521503170180",
    "tunisia": "5911332947419468671",
    "trinidad and tobago": "5911228635548750294",
    "togo": "5913423260757790970",
    "thailand": "5913617968805187987",
    "tanzania, united republic of": "5911418949844603556",
    "tanzania": "5911418949844603556",
    "tajikistan": "5911287639809463107",
    "switzerland": "5913271227505448072",
    "sweden": "5911156510162949403",
    "eswatini (swaziland)": "5913374525763883286",
    "swaziland": "5913374525763883286",
    "eswatini": "5913374525763883286",
    "suriname": "5913275539652611719",
    "sudan": "5911387497799094470",
    "spain": "5911193287967904547",
    "sri lanka": "5911293163137406640",
    "south sudan": "5911406262511211744",
    "south africa": "5911203119148044594",
    "somalia": "5911397852965244436",
    "solomon islands": "5911482712929080608",
    "slovenia": "5913431983836368644",
    "slovakia": "5913751666842145020",
    "singapore": "5911531460808051849",
    "sierra leone": "5911210450657218661",
    "seychelles": "5911185183364616913",
    "serbia": "5913592598433369871",
    "senegal": "5910995302860461643",
    "scotland": "5911460091336331851",
    "sao tome and principe": "5913574331937462345",
    "san marino": "5913587968458625465",
    "samoa": "5913325971158602854",
    "saint kitts and nevis": "5913691898077253637",
    "saint vincent and the grenadines": "5911318941531116255",
    "saint lucia": "5911243659344351824",
    "palestinian territory, occupied": "5913684768431541668",
    "palestine": "5913684768431541668",
    "rwanda": "5911455229433352234",
    "romania": "5913460373570195273",
    "qatar": "5911260864983339619",
    "puerto rico": "5911504350974317480",
    "portugal": "5911023653939581472",
    "philippines": "5911268638874145162",
    "peru": "5911207993935925780",
    "paraguay": "5911014265141072316",
    "papua new guinea": "5911107251183030903",
    "panama": "5913428968769327174",
    "palau": "5911283903187915549",
    "pakistan": "5913705895375672082",
    "oman": "5913570801474343473",
    "norway": "5913617397574537046",
    "nigeria": "5911143844304393105",
    "niger": "5911270086278124251",
    "new zealand": "5913640044937089340",
    "netherlands": "5913367645226275100",
    "nepal": "5913496520014958723",
    "namibia": "5911108535378252443",
    "mozambique": "5911333419865871464",
    "morocco": "5911482111633658301",
    "montenegro": "5913239436157522151",
    "mongolia": "5911041383564580038",
    "monaco": "5911245347266500057",
    "moldova, republic of": "5913456847402045950",
    "moldova": "5913456847402045950",
    "maldives": "5913501399097806832",
    "mali": "5911305266355245916",
    "malta": "5911023714069123567",
    "bermuda": "5913680005312811090",
    "martinique": "5911378005921370347",
    "marshall islands": "5913235935759175692",
    "mauritius": "5913291113204027321",
    "mexico": "5913687302462246518",
    "micronesia, federated states of": "5911271104185373336",
    "micronesia": "5911271104185373336",
    "malaysia": "5913654360063087453",
    "kenya": "5911154710571651231",
    "madagascar": "5913766918271012920",
    "republic of north macedonia": "5913394029210374721",
    "north macedonia": "5913394029210374721",
    "macedonia": "5913394029210374721",
    "luxembourg": "5913390842344640293",
    "lithuania": "5911172315642597775",
    "liechtenstein": "5911166650580734660",
    "libya": "5911236989260140996",
    "liberia": "5913324167272337727",
    "kiribati": "5911294443037660118",
    "kosovo": "5911433681582429010",
    "kuwait": "5913290705182134003",
    "kyrgyzstan": "5911202161370337549",
    "lao people's democratic republic": "5913718526874489279",
    "laos": "5913718526874489279",
    "latvia": "5913738489882480243",
    "lebanon": "5911504273664905447",
    "lesotho": "5911059881988723711",
    "indonesia": "5913479361620611038",
    "iran, islamic republic of": "5911308891307643032",
    "iran": "5911308891307643032",
    "iraq": "5911382442622587735",
    "ireland": "5913440715504881532",
    "israel": "5911471936856134692",
    "italy": "5913688444923547525",
    "jamaica": "5913232280742006526",
    "jordan": "5913234136167878475",
    "iceland": "5911047899029967246",
    "hungary": "5913767635530551104",
    "honduras": "5911406889576436289",
    "haiti": "5913459789454643194",
    "guyana": "5913579412883771480",
    "guinea-bissau": "5911398694778836149",
    "guinea": "5913471858312744319",
    "guatemala": "5913324858762072330",
    "grenada": "5913228063084121946",
    "greece": "5911210399117611448",
    "ghana": "5913391155877252952",
    "georgia": "5913434771270144023",
    "gambia": "5913657267755945883",
    "gabon": "5911037896051137264",
    "france": "5913605586414473124",
    "finland": "5911041344909873378",
    "fiji": "5911393832875856716",
    "ethiopia": "5911078333168227043",
    "dominican republic": "5911152099231536123",
    "timor-leste": "5911141915864076479",
    "ecuador": "5911273865849347408",
    "egypt": "5913694831539916769",
    "el salvador": "5913238624408703010",
    "england": "5913475719488344315",
    "estonia": "5910986042910969906",
    "dominica": "5911377121158107430",
    "djibouti": "5911407709915190157",
    "denmark": "5911206009661034712",
    "cyprus": "5911023550860366409",
    "croatia": "5913692684056269311",
    "costa rica": "5911261745451635030",
    "congo": "5911338788574990168",
    "congo, the democratic republic of the": "5913770362834783827",
    "democratic republic of the congo": "5913770362834783827",
    "comoros": "5911338582416560604",
    "cambodia": "5913699998385573485",
    "cameroon": "5911172109484167745",
    "canada": "5913623736946265914",
    "cape verde": "5913571501554012193",
    "central african republic": "5913443245240619222",
    "chad": "5913299849167507310",
    "czechia": "5911198691036764307",
    "czech republic": "5911198691036764307",
    "chile": "5911470957603592832",
    "colombia": "5913773060074246009",
    "burundi": "5913766441529642752",
    "botswana": "5911513782722499475",
    "bosnia and herzegovina": "5913700002680541032",
    "bosnia": "5913700002680541032",
    "bolivia": "5913638795101606133",
    "bhutan": "5913236734623093021",
    "benin": "5913735869952430547",
    "argentina": "5913573356979884082",
    "australia": "5913632326880858455",
    "austria": "5911338831524664592",
    "bahamas": "5911451643135660214",
    "bahrain": "5913581663446634403",
    "bangladesh": "5911365056594973179",
    "barbados": "5911016996740272263",
    "belgium": "5913529642802745141",
    "belize": "5913355005137522807",
    "antigua and barbuda": "5913389025573475085",
    "angola": "5913753316109586411",
    "andorra": "5911314702398396902",
    "algeria": "5913782968563800236",
    "albania": "5911357458797826163",
    "afghanistan": "5913492040364068694",
    "zimbabwe": "5911092502265336396",
    "cuba": "5431551436502611633",
    "korea, democratic people's republic of": "5434142701941437163",
    "north korea": "5434142701941437163",
    "venezuela": "5434009132753499322",
    "syrian arab republic": "5433910876786670092",
    "syria": "5433910876786670092",
    "myanmar": "5433666360003540231",
    "nicaragua": "5334807849418003620",
    "south korea": "5913371673905598425",
    "korea": "5913371673905598425",
    "equatorial guinea": "5911306279967529251",
    "greenland": "5292014752283774878",
    "faroe islands": "5296469342039327674",
    "côte d'ivoire (ivory coast)": "5222233374948602940",
    "ivory coast": "5222233374948602940",
    "côte d'ivoire": "5222233374948602940",
    "brunei": "5911336409163109113",
    "bulgaria": "5294329219965272288",
    "burkina faso": "5913407764515786948",
    "eritrea": "5433723401464198287",
    "malawi": "5433968339154122439",
    "mauritania": "5433859405898594234",
    "nauru": "5434131139889478358",
    "saudi arabia": "4985897134424328239",
    "tonga": "5433640100573491806",
    "tuvalu": "5433684690923961019",
    "taiwan": "5366187256937726720",
    "hong kong": "5292166459118606932",
    "macau": "6323557758096377611",
    "anguilla": "5780471598922337683",
    "aruba": "5780471598922337683",
    "british virgin islands": "5780471598922337683",
    "cayman islands": "5780471598922337683",
    "curacao": "5780471598922337683",
    "falkland islands": "5780471598922337683",
    "french guiana": "5780471598922337683",
    "guadeloupe": "5780471598922337683",
    "guam": "5780471598922337683",
    "mayotte": "5780471598922337683",
    "montserrat": "5780471598922337683",
    "new caledonia": "5780471598922337683",
    "niue": "5780471598922337683",
    "norfolk island": "5780471598922337683",
    "northern mariana islands": "5780471598922337683",
    "pitcairn islands": "5780471598922337683",
    "reunion": "5780471598922337683",
    "saint helena": "5780471598922337683",
    "tokelau": "5780471598922337683",
    "turks and caicos islands": "5780471598922337683",
    "us virgin islands": "5780471598922337683",
    "wallis and futuna": "5780471598922337683",
    "western sahara": "5780471598922337683",
    "cook islands": "5780471598922337683",
    "french polynesia": "5780471598922337683",
    "gibraltar": "5780471598922337683",
    "svalbard and jan mayen": "5780471598922337683",
    "aland islands": "5780471598922337683",
    "jersey": "5780471598922337683",
    "guernsey": "5780471598922337683",
    "isle of man": "5226538255029121667",
    "saint pierre and miquelon": "5780471598922337683",
    "sint maarten": "5461113820955027461",
    "bonaire": "5780471598922337683",
}

# --- Telegram Latest Feature Check (CopyTextButton) ---
try:
    from telebot.types import CopyTextButton
    HAS_COPY_BTN = True
except ImportError:
    HAS_COPY_BTN = False

# ========================================================
# --- STYLE & CUSTOM EMOJI MAPS WITHOUT COLLISION BAGS ---
# ========================================================
_old_inline_dict = InlineKeyboardButton.to_dict
def _new_inline_dict(self):
    d = _old_inline_dict(self)
    
    style = getattr(self, 'style', None)
    if style:
        d['style'] = style
        
    emoji_id = getattr(self, 'icon_custom_emoji_id', None)
    if emoji_id:
        val = str(emoji_id).strip()
        if val:
            d['icon_custom_emoji_id'] = val

    # CopyTextButton support — inject after creation to bypass constructor TypeError
    copy_text_obj = getattr(self, '_copy_text_obj', None)
    if copy_text_obj is not None:
        # Remove any callback_data fallback, inject real copy_text
        d.pop('callback_data', None)
        try:
            d['copy_text'] = copy_text_obj.to_dict() if hasattr(copy_text_obj, 'to_dict') else {'text': str(copy_text_obj)}
        except Exception:
            d['copy_text'] = {'text': str(copy_text_obj)}
            
    return d
InlineKeyboardButton.to_dict = _new_inline_dict

_old_kb_dict = KeyboardButton.to_dict
def _new_kb_dict(self):
    d = _old_kb_dict(self)
    
    style = getattr(self, 'style', None)
    if style:
        d['style'] = style
        
    emoji_id = getattr(self, 'icon_custom_emoji_id', None)
    if emoji_id:
        val = str(emoji_id).strip()
        if val:
            d['icon_custom_emoji_id'] = val
            
    return d
KeyboardButton.to_dict = _new_kb_dict

# Escapes dynamic content beautifully to prevent Telegram HTML parse crashes
def escape_html(text):
    return str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

# Safe, ultra-compatible copy text wrappers
def ibtn(text, callback_data=None, url=None, style=None, copy_text_str=None, custom_emoji_id=None):
    kwargs = {'text': text}
    if callback_data: kwargs['callback_data'] = callback_data
    if url: kwargs['url'] = url

    # Copy text: always use a dummy callback_data first (required by constructor),
    # then override via _copy_text_obj in to_dict patch.
    if copy_text_str:
        kwargs['callback_data'] = f"__copy__"

    try:
        b = InlineKeyboardButton(**kwargs)
    except TypeError:
        kwargs.pop('callback_data', None)
        kwargs['callback_data'] = "__copy__"
        b = InlineKeyboardButton(**kwargs)

    # Inject copy_text via attribute (serialized by patched to_dict)
    if copy_text_str:
        if HAS_COPY_BTN:
            try:
                b._copy_text_obj = CopyTextButton(text=str(copy_text_str))
            except Exception:
                b._copy_text_obj = type('CT', (), {'to_dict': lambda self: {'text': str(copy_text_str)}})()
        else:
            # Fallback: store raw string, to_dict will serialize as {'text': ...}
            b._copy_text_obj = type('CT', (), {'to_dict': lambda self, s=copy_text_str: {'text': str(s)}})()

    if style:
        try: b.style = style
        except AttributeError: pass

    emoji_val = str(custom_emoji_id).strip() if custom_emoji_id else None
    if emoji_val:
        try: b.icon_custom_emoji_id = emoji_val
        except AttributeError: pass

    return b

def rbtn(text, style=None, custom_emoji_id=None):
    b = KeyboardButton(text=text)
    
    if style:
        try: b.style = style
        except AttributeError: pass
        
    emoji_val = str(custom_emoji_id).strip() if custom_emoji_id else None
    if emoji_val:
        try: b.icon_custom_emoji_id = emoji_val
        except AttributeError: pass
        
    return b

bot = telebot.TeleBot(TOKEN, num_threads=100)
BOT_USERNAME_CACHE = None

def get_bot_username():
    global BOT_USERNAME_CACHE
    if not BOT_USERNAME_CACHE:
        try:
            BOT_USERNAME_CACHE = bot.get_me().username
        except:
            BOT_USERNAME_CACHE = "Mino_SMS_boT"
    return BOT_USERNAME_CACHE

DATA_FILE = "Data_File.json"
db_lock = threading.RLock()
active_polls = {}
db_cache = None  

# --- ADMIN PANEL ACTIVE IN-PLACE MENUS TRACKER ---
admin_active_menus = {}

def save_active_menu(chat_id, message):
    if message:
        admin_active_menus[str(chat_id)] = message.message_id

# --- UNIQUE OTP REWARD TRACKER ---
credited_numbers = set()

# ============================================
# --- DATABASE & UTILS (AUTO SCHEMA REPAIR) ---
# ============================================
def load_data():
    global db_lock, db_cache
    with db_lock:
        if db_cache is not None:
            return db_cache
            
        default_data = {
            "users": [], 
            "banned_users": [], 
            "services_data": {}, 
            "forward_groups": [], 
            "balances": {}, 
            "wallets": {}, 
            "referred_by": {}, 
            "referrals": {},
            "pending_withdrawals": {}, 
            "admins": [7940416120], 
            "maintenance_mode": False,
            "maintenance_message": "<b>⚠️ System under maintenance. Please try again later.</b>",
            "texts": {
                "welcome": '<tg-emoji emoji-id="5970074171449808121">🎁</tg-emoji> <b>╔══════════════════════╗</b>\n<b>         🤖 𝐑𝐌 𝐗𝐄𝐋 𝐁𝐎𝐓 🤖</b>\n<tg-emoji emoji-id="5970074171449808121">🎁</tg-emoji> <b>╚══════════════════════╝</b>\n\n<tg-emoji emoji-id="6237550015791765281">⭐</tg-emoji> <b>𝐔𝐋𝐓𝐑𝐀 𝐅𝐀𝐒𝐓 𝐎𝐓𝐏 𝐑𝐄𝐂𝐄𝐈𝐕𝐄𝐑</b> <tg-emoji emoji-id="6237550015791765281">⭐</tg-emoji>\n\n━━━━━━━━━━━━━━━━━━━━━━━━\n<tg-emoji emoji-id="6298670698948724690">✅</tg-emoji> <b>Instant OTP Delivery</b>\n<tg-emoji emoji-id="5296369303661067030">🔑</tg-emoji> <b>Premium Numbers Available</b>\n<tg-emoji emoji-id="5190899075968441286">💰</tg-emoji> <b>Earn Balance Per OTP</b>\n<tg-emoji emoji-id="5420396762189831222">🔗</tg-emoji> <b>Referral Bonus System</b>\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n<i>👇 Select an option from the menu below</i>',
                "support": '<b>Support</b>\n\nClick the button below to contact support.',
                "support_link": "https://t.me/rahi455",
                "otp_group_link": "https://t.me/rmmtzotpgroup",
                "main_channel_link": "https://t.me/rmmethodzone",
                "renge_group_link": "https://t.me/newotppannel",
                "btn_get_number": "GET NUMBER",
                "btn_balance": "BALANCE",
                "btn_refer": "REFER AND EARN",
                "btn_support": "SUPPORT"
            },
            "custom_emojis": DEFAULT_CUSTOM_EMOJIS,
            "api_key": NEXA_API_KEY,
            "panel_config": dict(PANEL_DEFAULTS),
            "leaderboard": {
                "last_reset": 0.0,
                "stats": {}
            },
            "settings": {
                "otp_bonus": 0.0081, 
                "ref_bonus": 0.01, 
                "max_numbers": 3, 
                "min_withdraw": 0.3,
                "leaderboard_reset_days": 3,
                "force_join_channels": [],
                "admin_alerts": True,
                "only_member_join_alert": True
            }
        }
        
        def sanitize(loaded, defaults):
            if not isinstance(loaded, dict):
                return defaults.copy()
            for key, default_val in defaults.items():
                if key not in loaded:
                    loaded[key] = default_val
                else:
                    if isinstance(default_val, dict):
                        loaded[key] = sanitize(loaded[key], default_val)
                    elif isinstance(default_val, list):
                        if not isinstance(loaded[key], list):
                            loaded[key] = default_val.copy()
                    elif isinstance(default_val, float):
                        try: loaded[key] = float(loaded[key])
                        except: loaded[key] = default_val
                    elif isinstance(default_val, int):
                        try: loaded[key] = int(loaded[key])
                        except: loaded[key] = default_val
                    elif isinstance(default_val, str):
                        loaded[key] = str(loaded[key])
            return loaded

        if not os.path.exists(DATA_FILE):
            with open(DATA_FILE, "w", encoding='utf-8') as f: 
                json.dump(default_data, f, indent=2)
            db_cache = default_data
            return db_cache
            
        try:
            with open(DATA_FILE, "r", encoding='utf-8') as f:
                raw = f.read().strip()
                if not raw:
                    loaded_data = default_data
                else:
                    loaded_data = json.loads(raw)
        except Exception:
            loaded_data = default_data

        loaded_data = sanitize(loaded_data, default_data)
        
        lboard = loaded_data.setdefault("leaderboard", {"last_reset": 0.0, "stats": {}})
        if not isinstance(lboard, dict):
            loaded_data["leaderboard"] = {"last_reset": time.time(), "stats": {}}
        else:
            try:
                float(lboard.get("last_reset", 0.0))
            except:
                lboard["last_reset"] = time.time()
            if not isinstance(lboard.get("stats"), dict):
                lboard["stats"] = {}
                
        srv_data = loaded_data.setdefault("services_data", {})
        if not isinstance(srv_data, dict):
            loaded_data["services_data"] = {}
        else:
            to_del = []
            for s_id, s_val in srv_data.items():
                if not isinstance(s_val, dict) or "name" not in s_val:
                    to_del.append(s_id)
                else:
                    s_val.setdefault("countries", {})
                    if not isinstance(s_val["countries"], dict):
                        s_val["countries"] = {}
                    else:
                        for c_id, c_val in srv_data[s_id]["countries"].items():
                            if not isinstance(c_val, dict) or "name" not in c_val:
                                srv_data[s_id]["countries"][c_id] = {"name": str(c_id), "range": ""}
                            else:
                                c_val.setdefault("range", "")
            for s_id in to_del:
                del srv_data[s_id]

        db_cache = loaded_data
        return db_cache

def _write_data_file(data):
    try:
        import copy
        snapshot = copy.deepcopy(data)
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, indent=2)
    except Exception:
        pass

def save_data(data):
    global db_lock, db_cache
    with db_lock:
        db_cache = data
    threading.Thread(target=_write_data_file, args=(data,), daemon=True).start()

def is_admin(user_id):
    data = load_data()
    admins = data.setdefault("admins", [ADMIN_ID])
    return int(user_id) in [int(a) for a in admins] or int(user_id) == ADMIN_ID

def is_banned(chat_id):
    data = load_data()
    return str(chat_id) in data.get("banned_users", [])

def get_country_flag(country_name):
    cn_lower = str(country_name).lower().strip()
    fallback = "🌍"
    if cn_lower in PREMIUM_FLAGS:
        eid = PREMIUM_FLAGS[cn_lower]
        return f'<tg-emoji emoji-id="{eid}">{fallback}</tg-emoji>'
    for k, v in PREMIUM_FLAGS.items():
        if k in cn_lower or cn_lower in k:
            return f'<tg-emoji emoji-id="{v}">{fallback}</tg-emoji>'
    return get_emoji_tag("emj_country", fallback)

def get_premium_flag_id(country_name):
    """Return premium flag emoji ID (for button icon_custom_emoji_id) from country name."""
    cn_lower = str(country_name).lower().strip()
    if cn_lower in PREMIUM_FLAGS:
        return PREMIUM_FLAGS[cn_lower]
    for k, v in PREMIUM_FLAGS.items():
        if k in cn_lower or cn_lower in k:
            return v
    return ""

def get_unicode_flag(country_name):
    country_to_code = {
        "bangladesh": "BD", "india": "IN", "pakistan": "PK", "russia": "RU",
        "russian federation": "RU", "ukraine": "UA", "poland": "PL",
        "united states": "US", "usa": "US", "united kingdom": "GB", "uk": "GB",
        "uzbekistan": "UZ", "turkey": "TR", "belarus": "BY", "brazil": "BR",
        "vietnam": "VN", "indonesia": "ID", "philippines": "PH", "china": "CN",
        "germany": "DE", "france": "FR", "spain": "ES", "italy": "IT",
        "japan": "JP", "south korea": "KR", "myanmar": "MM", "thailand": "TH",
        "malaysia": "MY", "egypt": "EG", "nigeria": "NG", "ghana": "GH",
        "kenya": "KE", "ethiopia": "ET", "tanzania": "TZ", "uganda": "UG",
        "morocco": "MA", "algeria": "DZ", "cameroon": "CM", "angola": "AO",
        "mali": "ML", "ivory coast": "CI", "togo": "TG", "senegal": "SN",
        "sudan": "SD", "south africa": "ZA", "argentina": "AR", "colombia": "CO",
        "mexico": "MX", "peru": "PE", "chile": "CL", "venezuela": "VE",
        "canada": "CA", "australia": "AU", "netherlands": "NL", "portugal": "PT",
        "sweden": "SE", "norway": "NO", "denmark": "DK", "finland": "FI",
        "greece": "GR", "romania": "RO", "hungary": "HU", "czech republic": "CZ",
        "austria": "AT", "switzerland": "CH", "belgium": "BE", "slovakia": "SK",
        "estonia": "EE", "latvia": "LV", "lithuania": "LT", "croatia": "HR",
        "serbia": "RS", "albania": "AL", "moldova": "MD", "armenia": "AM",
        "georgia": "GE", "azerbaijan": "AZ", "kazakhstan": "KZ", "kyrgyzstan": "KG",
        "tajikistan": "TJ", "turkmenistan": "TM", "mongolia": "MN",
        "nepal": "NP", "sri lanka": "LK", "cambodia": "KH", "laos": "LA",
        "singapore": "SG", "taiwan": "TW", "hong kong": "HK",
        "iran": "IR", "iraq": "IQ", "saudi arabia": "SA", "uae": "AE",
        "united arab emirates": "AE", "qatar": "QA", "kuwait": "KW",
        "bahrain": "BH", "oman": "OM", "jordan": "JO", "lebanon": "LB",
        "syria": "SY", "israel": "IL", "yemen": "YE", "afghanistan": "AF",
        "zimbabwe": "ZW", "zambia": "ZM", "mozambique": "MZ", "somalia": "SO",
        "liberia": "LR", "guinea": "GN", "burundi": "BI", "rwanda": "RW",
        "custom number": "",
    }
    cn = str(country_name).lower().strip()
    code = country_to_code.get(cn, "")
    if not code:
        for k, v in country_to_code.items():
            if k in cn or cn in k:
                code = v
                break
    if not code:
        return ""
    flag = "".join(chr(0x1F1E6 + ord(c) - ord('A')) for c in code.upper())
    return flag

def get_country_info(number):
    """Reference bot থেকে নেওয়া — range prefix দিয়ে (flag, country_name) return করে।"""
    country_map = {
        "2376": ("🇨🇲", "Cameroon"), "2250": ("🇨🇮", "Ivory Coast"), "2613": ("🇲🇬", "Madagascar"),
        "4077": ("🇷🇴", "Romania"), "447": ("🇬🇧", "UK (Virtual)"), "1201": ("🇺🇸", "USA (Virtual)"),
        "1302": ("🇺🇸", "USA (Virtual)"), "1415": ("🇺🇸", "USA (Virtual)"), "1212": ("🇺🇸", "USA (Virtual)"),
        "1917": ("🇺🇸", "USA (Virtual)"), "1646": ("🇺🇸", "USA (Virtual)"), "1347": ("🇺🇸", "USA (Virtual)"),
        "237": ("🇨🇲", "Cameroon"), "225": ("🇨🇮", "Ivory Coast"), "261": ("🇲🇬", "Madagascar"),
        "20": ("🇪🇬", "Egypt"), "27": ("🇿🇦", "South Africa"), "234": ("🇳🇬", "Nigeria"),
        "254": ("🇰🇪", "Kenya"), "233": ("🇬🇭", "Ghana"), "212": ("🇲🇦", "Morocco"),
        "213": ("🇩🇿", "Algeria"), "216": ("🇹🇳", "Tunisia"), "218": ("🇱🇾", "Libya"),
        "249": ("🇸🇩", "Sudan"), "251": ("🇪🇹", "Ethiopia"), "252": ("🇸🇴", "Somalia"),
        "253": ("🇩🇯", "Djibouti"), "255": ("🇹🇿", "Tanzania"), "256": ("🇺🇬", "Uganda"),
        "257": ("🇧🇮", "Burundi"), "258": ("🇲🇿", "Mozambique"), "260": ("🇿🇲", "Zambia"),
        "263": ("🇿🇼", "Zimbabwe"), "264": ("🇳🇦", "Namibia"), "265": ("🇲🇼", "Malawi"),
        "266": ("🇱🇸", "Lesotho"), "267": ("🇧🇼", "Botswana"), "268": ("🇸🇿", "Eswatini"),
        "269": ("🇰🇲", "Comoros"), "220": ("🇬🇲", "Gambia"), "221": ("🇸🇳", "Senegal"),
        "222": ("🇲🇷", "Mauritania"), "223": ("🇲🇱", "Mali"), "224": ("🇬🇳", "Guinea"),
        "226": ("🇧🇫", "Burkina Faso"), "227": ("🇳🇪", "Niger"), "228": ("🇹🇬", "Togo"),
        "229": ("🇧🇯", "Benin"), "230": ("🇲🇺", "Mauritius"), "231": ("🇱🇷", "Liberia"),
        "232": ("🇸🇱", "Sierra Leone"), "235": ("🇹🇩", "Chad"), "236": ("🇨🇫", "Central African Republic"),
        "238": ("🇨🇻", "Cape Verde"), "239": ("🇸🇹", "Sao Tome"), "240": ("🇬🇶", "Equatorial Guinea"),
        "241": ("🇬🇦", "Gabon"), "242": ("🇨🇬", "Congo"), "243": ("🇨🇩", "DR Congo"),
        "244": ("🇦🇴", "Angola"), "245": ("🇬🇼", "Guinea-Bissau"), "250": ("🇷🇼", "Rwanda"),
        "291": ("🇪🇷", "Eritrea"), "40": ("🇷🇴", "Romania"), "44": ("🇬🇧", "United Kingdom"),
        "33": ("🇫🇷", "France"), "49": ("🇩🇪", "Germany"), "39": ("🇮🇹", "Italy"),
        "34": ("🇪🇸", "Spain"), "31": ("🇳🇱", "Netherlands"), "32": ("🇧🇪", "Belgium"),
        "41": ("🇨🇭", "Switzerland"), "43": ("🇦🇹", "Austria"), "46": ("🇸🇪", "Sweden"),
        "47": ("🇳🇴", "Norway"), "45": ("🇩🇰", "Denmark"), "358": ("🇫🇮", "Finland"),
        "351": ("🇵🇹", "Portugal"), "353": ("🇮🇪", "Ireland"), "36": ("🇭🇺", "Hungary"),
        "48": ("🇵🇱", "Poland"), "380": ("🇺🇦", "Ukraine"), "370": ("🇱🇹", "Lithuania"),
        "371": ("🇱🇻", "Latvia"), "372": ("🇪🇪", "Estonia"), "373": ("🇲🇩", "Moldova"),
        "374": ("🇦🇲", "Armenia"), "375": ("🇧🇾", "Belarus"), "381": ("🇷🇸", "Serbia"),
        "382": ("🇲🇪", "Montenegro"), "385": ("🇭🇷", "Croatia"), "386": ("🇸🇮", "Slovenia"),
        "387": ("🇧🇦", "Bosnia"), "389": ("🇲🇰", "North Macedonia"), "352": ("🇱🇺", "Luxembourg"),
        "354": ("🇮🇸", "Iceland"), "355": ("🇦🇱", "Albania"), "356": ("🇲🇹", "Malta"),
        "357": ("🇨🇾", "Cyprus"), "359": ("🇧🇬", "Bulgaria"), "421": ("🇸🇰", "Slovakia"),
        "420": ("🇨🇿", "Czech Republic"),
        "1": ("🇺🇸", "United States"), "7": ("🇷🇺", "Russia"),
        "880": ("🇧🇩", "Bangladesh"), "86": ("🇨🇳", "China"), "81": ("🇯🇵", "Japan"),
        "82": ("🇰🇷", "South Korea"), "84": ("🇻🇳", "Vietnam"), "66": ("🇹🇭", "Thailand"),
        "62": ("🇮🇩", "Indonesia"), "60": ("🇲🇾", "Malaysia"), "65": ("🇸🇬", "Singapore"),
        "63": ("🇵🇭", "Philippines"), "95": ("🇲🇲", "Myanmar"), "94": ("🇱🇰", "Sri Lanka"),
        "977": ("🇳🇵", "Nepal"), "93": ("🇦🇫", "Afghanistan"), "98": ("🇮🇷", "Iran"),
        "90": ("🇹🇷", "Turkey"), "964": ("🇮🇶", "Iraq"), "963": ("🇸🇾", "Syria"),
        "961": ("🇱🇧", "Lebanon"), "962": ("🇯🇴", "Jordan"), "965": ("🇰🇼", "Kuwait"),
        "966": ("🇸🇦", "Saudi Arabia"), "967": ("🇾🇪", "Yemen"), "968": ("🇴🇲", "Oman"),
        "971": ("🇦🇪", "UAE"), "972": ("🇮🇱", "Israel"), "973": ("🇧🇭", "Bahrain"),
        "974": ("🇶🇦", "Qatar"), "994": ("🇦🇿", "Azerbaijan"), "995": ("🇬🇪", "Georgia"),
        "996": ("🇰🇬", "Kyrgyzstan"), "992": ("🇹🇯", "Tajikistan"), "993": ("🇹🇲", "Turkmenistan"),
        "998": ("🇺🇿", "Uzbekistan"), "855": ("🇰🇭", "Cambodia"), "856": ("🇱🇦", "Laos"),
        "976": ("🇲🇳", "Mongolia"), "91": ("🇮🇳", "India"), "92": ("🇵🇰", "Pakistan"),
        "55": ("🇧🇷", "Brazil"), "52": ("🇲🇽", "Mexico"), "54": ("🇦🇷", "Argentina"),
        "57": ("🇨🇴", "Colombia"), "51": ("🇵🇪", "Peru"), "58": ("🇻🇪", "Venezuela"),
        "56": ("🇨🇱", "Chile"), "593": ("🇪🇨", "Ecuador"), "591": ("🇧🇴", "Bolivia"),
        "595": ("🇵🇾", "Paraguay"), "598": ("🇺🇾", "Uruguay"), "502": ("🇬🇹", "Guatemala"),
        "61": ("🇦🇺", "Australia"), "64": ("🇳🇿", "New Zealand"),
    }
    clean_num = str(number).replace('+', '').replace(' ', '').replace('-', '').strip()
    for prefix in sorted(country_map.keys(), key=len, reverse=True):
        if clean_num.startswith(prefix):
            return country_map[prefix]
    return ("🌍", "Unknown")

def detect_country_by_prefix(range_val):
    flag, name = get_country_info(range_val)
    return name, flag

def get_country_short_code(country_name):
    cn = str(country_name).lower().strip()
    mapping = {
        "mali": "ML",
        "myanmar": "MM", "uzbekistan": "UZ", "lebanon": "LB", "bangladesh": "BD", 
        "india": "IN", "pakistan": "PK", "russia": "RU", "indonesia": "ID",
        "ukraine": "UA", "egypt": "EG", "vietnam": "VN", "turkey": "TR",
        "ivory coast": "CI", "usa": "US", "uk": "GB", "philippines": "PH", "liberia": "LR",
        "custom number": "CUSTOM"
    }
    for k, v in mapping.items():
        if k in cn: return v
    return cn[:2].upper()

def get_country_premium_emoji(country_name):
    if country_name == "Custom Number" or country_name == "Custom Range":
        return get_emoji_tag("emj_changing")
    return get_country_flag(country_name)

def get_emoji_tag(key, fallback=None):
    placeholders = {
        "emj_support": "💬", "emj_number": "📱", "emj_wallet": "💳", "emj_profile": "👤",
        "emj_refer": "👥", "emj_bkash": "🏦", "emj_rocket": "🚀", "emj_binance": "🪙",
        "emj_country": "🌍", "emj_instagram": "📸", "emj_facebook": "📘", "emj_tiktok": "🎵",
        "emj_whatsapp": "💬", "emj_telegram": "✈️", "emj_admin_panel": "👑", "emj_ban": "🚫",
        "emj_broadcast": "📢", "emj_otp_coming": "⏳", "emj_otp_received": "⭐", "emj_message": "✉️",
        "emj_stop": "🛑", "emj_successful": "✅", "emj_changing": "🔄", "emj_add": "➕",
        "emj_link": "🔗", "emj_nagad": "🟠", "emj_cross": "❌", "emj_gift": "🎁",
        "emj_up": "📈", "emj_support_btn": "💬", "emj_key": "🔑", "emj_done": "✅",
        "emj_search": "🔍", "emj_share": "📢", "emj_otp_group": "👥", "emj_gen_number": "⏳",
        "emj_copy_link": "📋"
    }
    if not fallback:
        fallback = placeholders.get(key, "⭐")

    fallback = str(fallback).replace("\ufe0f", "")
    if len(fallback) > 1 and not (len(fallback) == 2 and ord(fallback[0]) >= 0xd800):
        fallback = "⭐"

    # DEFAULT_CUSTOM_EMOJIS সবসময় প্রথমে চেক করা হয় (hardcoded premium IDs)
    emoji_id = DEFAULT_CUSTOM_EMOJIS.get(key, "").strip()
    if not emoji_id:
        # fallback: Data_File.json থেকে নাও
        data = load_data()
        emojis = data.setdefault("custom_emojis", {})
        emoji_id = emojis.get(key, "").strip()

    if emoji_id:
        return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'
    return fallback

def get_emoji_id(key):
    # typo fix
    if key in ("emj_instragram", "instragram"):
        key = "emj_instagram"

    # DEFAULT_CUSTOM_EMOJIS সবসময় প্রথমে চেক করা হয়
    val = DEFAULT_CUSTOM_EMOJIS.get(key, "").strip()
    if val:
        return val

    # fallback: Data_File.json থেকে নাও
    data = load_data()
    emojis = data.setdefault("custom_emojis", {})
    val = emojis.get(key, "").strip()
    return val if val else None

def get_service_emoji(service_name):
    sn = str(service_name).lower()
    if 'facebook' in sn: return get_emoji_tag("emj_facebook")
    if 'tiktok' in sn: return get_emoji_tag("emj_tiktok")
    if 'telegram' in sn: return get_emoji_tag("emj_telegram")
    if 'whatsapp' in sn: return get_emoji_tag("emj_whatsapp")
    if 'instagram' in sn or 'instragram' in sn: return get_emoji_tag("emj_instagram")
    if 'custom number' in sn: return get_emoji_tag("emj_changing")
    return "" 

def mask_number(phone):
    phone_str = str(phone).replace('+', '').strip()
    if len(phone_str) >= 8:
        return f"{phone_str[:4]}•••{phone_str[-4:]}"
    elif len(phone_str) >= 6:
        return f"{phone_str[:3]}•••{phone_str[-3:]}"
    return phone_str

def is_subscribed(user_id):
    if int(user_id) == ADMIN_ID or is_admin(user_id): return True
    data = load_data()
    channels = data.setdefault("settings", {}).setdefault("force_join_channels", [])
    if not channels: return True
    
    for ch in channels:
        try:
            member = bot.get_chat_member(ch, user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                return False
        except Exception:
            return False
    return True

def send_force_join(chat_id):
    data = load_data()
    channels = data["settings"].setdefault("force_join_channels", [])
    
    text = f'{get_emoji_tag("emj_stop")} <b>Please join our channels to use the bot!</b>'
    markup = InlineKeyboardMarkup()
    
    for idx, ch in enumerate(channels, 1):
        url = f"https://t.me/{ch.replace('@', '')}" if ch.startswith("@") else ch
        markup.add(ibtn(f"Join Channel {idx}", url=url, style="primary", custom_emoji_id=get_emoji_id("emj_link")))
        
    markup.add(ibtn("Check Joined", callback_data="chk_joined", style="success", custom_emoji_id=get_emoji_id("emj_successful")))
    bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)

# ============================================
# --- ANTIBUG NEXT STEP CHECKER & OTP EXTRACT ---
# ============================================
def is_menu_button(text):
    if not text:
        return False
    data = load_data()
    texts = data.setdefault("texts", {})
    menu_buttons = [
        texts.get("btn_get_number", "GET NUMBER"),
        "Custom Number",
        texts.get("btn_balance", "BALANCE"),
        texts.get("btn_refer", "REFER AND EARN"),
        "PROFILE",
        "LEADERBOARD",
        texts.get("btn_support", "SUPPORT"),
        "Renge Group",
        "ADMIN PANEL"
    ]
    return text.strip() in menu_buttons

def send_number_fetch_animation(chat_id, msg_id, stop_event):
    """নম্বর ফেচ হওয়ার সময় animation চলে background thread-এ।"""
    _e = '<tg-emoji emoji-id="5253737930727384427">⭐</tg-emoji>'
    while not stop_event.is_set():
        try:
            bot.edit_message_text(_e, chat_id=chat_id, message_id=msg_id, parse_mode="HTML")
        except:
            pass
        stop_event.wait(0.1)

def send_otp_animation(chat_id):
    """OTP আসার পরে animation দেখায়।"""
    _e1 = '<tg-emoji emoji-id="5440621591387980068">⚡</tg-emoji>'
    _e2 = '<tg-emoji emoji-id="5375338737028841420">⏳</tg-emoji>'
    _e3 = '<tg-emoji emoji-id="5253938436980632246">💫</tg-emoji>'
    _e4 = '<tg-emoji emoji-id="5253737930727384427">✅</tg-emoji>'
    frames = [
        f"{_e1}",
        f"{_e1} {_e2}",
        f"{_e2} {_e1} {_e2}",
        f"{_e1} {_e2} {_e1}",
        f"{_e2} {_e3} {_e2}",
        f"{_e3} {_e1} {_e3}",
        f"{_e1} {_e3} {_e2}",
        f"{_e2} {_e1} {_e3}",
        f"{_e3} {_e2} {_e1}",
        f"{_e4} <b>OTP RECEIVED!</b> {_e4}",
    ]
    try:
        anim_msg = bot.send_message(chat_id, frames[0], parse_mode="HTML")
        for frame in frames[1:]:
            time.sleep(0.1)
            try:
                bot.edit_message_text(frame, chat_id, anim_msg.message_id, parse_mode="HTML")
            except:
                pass
        time.sleep(0.3)
        try:
            bot.delete_message(chat_id, anim_msg.message_id)
        except:
            pass
    except:
        pass

def extract_otp(sms_text):
    # Search for hyphenated format first (e.g. 453-796)
    match = re.search(r'\b\d{3}[-\s]\d{3}\b', sms_text)
    if match:
        return match.group(0)
    # Search for standard 4-8 digit OTP code
    match = re.search(r'\b\d{4,8}\b', sms_text)
    if match:
        return match.group(0)
    return "Not Extracted"

# ============================================
# --- USER UI FUNCTIONS ---
# ============================================
def get_main_menu(chat_id):
    data = load_data()
    texts = data.setdefault("texts", {})
    btn_get_number = texts.get("btn_get_number", "GET NUMBER")
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        rbtn(btn_get_number, "success", custom_emoji_id="5251514997388897766"),
        rbtn("Custom Number", "danger", custom_emoji_id="5253737930727384427")
    )
    markup.add(
        rbtn("PROFILE", "primary", custom_emoji_id="5251671733630431622"),
        rbtn("LEADERBOARD", "success", custom_emoji_id="5282843764451195532")
    )
    if is_admin(chat_id):
        markup.add(rbtn("ADMIN PANEL", "danger", custom_emoji_id="5251691769652867056"))
    return markup

def _build_app_markup_and_send(chat_id, message_id):
    """Background thread: fetch live ranges, then edit message with app buttons."""
    # Clear cache to force fresh fetch
    _live_ranges_cache["data"] = None
    _live_ranges_cache["updated_at"] = 0

    top_by_app, err = fetch_live_ranges_by_app()

    if err or not top_by_app:
        # Retry once after short pause
        time.sleep(1)
        _live_ranges_cache["data"] = None
        _live_ranges_cache["updated_at"] = 0
        top_by_app, err = fetch_live_ranges_by_app()

    if not top_by_app:
        # Final fallback: admin-configured services
        data = load_data()
        services = data.get("services_data", {})
        if not services:
            retry_markup = InlineKeyboardMarkup().add(
                ibtn("🔄 Retry", callback_data="retry_get_number", style="primary", custom_emoji_id=get_emoji_id("emj_changing"))
            )
            err_text = f'{get_emoji_tag("emj_cross")} <b>Could not load apps.</b>\n<i>Server is busy. Tap Retry to try again.</i>'
            try: bot.edit_message_text(err_text, chat_id=chat_id, message_id=message_id, parse_mode="HTML", reply_markup=retry_markup)
            except: pass
            return
        markup = InlineKeyboardMarkup(row_width=2)
        for srv_id, srv in services.items():
            if not isinstance(srv, dict) or "name" not in srv: continue
            markup.add(ibtn(srv['name'], callback_data=f"usr_s|{srv_id}", style="primary",
                            custom_emoji_id=get_app_emoji_id_for_service(srv['name'])))
        text = f'{get_emoji_tag("emj_number")} <b>Select a Service:</b>'
        try:
            msg = bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, parse_mode="HTML", reply_markup=markup)
            save_active_menu(chat_id, msg)
        except:
            msg = bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)
            save_active_menu(chat_id, msg)
        return

    # Build 2-per-row app buttons from live ranges
    markup = InlineKeyboardMarkup(row_width=2)
    row = []
    for app_name, ranges in top_by_app.items():
        if not ranges: continue
        # শুধু ALLOWED_APPS-এর সার্ভিস দেখাবে
        app_lower = app_name.lower()
        if not any(allowed in app_lower for allowed in ALLOWED_APPS):
            continue
        safe_app = app_name[:20].replace("|", "")
        btn = ibtn(app_name, callback_data=f"view_app_ranges|{safe_app}",
                   style="primary", custom_emoji_id=get_app_emoji_id_for_service(app_name))
        row.append(btn)
        if len(row) == 2:
            markup.row(*row)
            row = []
    if row:
        markup.row(*row)

    text = f'{get_emoji_tag("emj_number")} <b>SELECT APP TO GET NUMBER</b>\n━━━━━━━━━━━━━━━━━━━━━'
    try:
        msg = bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, parse_mode="HTML", reply_markup=markup)
        save_active_menu(chat_id, msg)
    except:
        msg = bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)
        save_active_menu(chat_id, msg)


def show_app_ranges(chat_id, app_name, message_id):
    """Reference bot flow: Service → Live Country List → Number
    Per-user session এ country→ranges store করে, sel_cty|{idx} callback ব্যবহার করে (always <15 bytes)."""
    top_by_app, err = fetch_live_ranges_by_app()
    if err or not top_by_app:
        try:
            bot.edit_message_text(
                f'{get_emoji_tag("emj_cross")} <b>Could not load countries. Try again.</b>',
                chat_id=chat_id, message_id=message_id, parse_mode="HTML"
            )
        except: pass
        return

    # App name case-insensitive match করে ranges নাও
    raw_ranges = None
    for key in top_by_app:
        val = top_by_app[key]
        if key.lower() == app_name.lower():
            # voltx/stex/fastxotp: {"ranges":[...], ...} | zenex: [rng1, rng2, ...]
            raw_ranges = val.get("ranges", []) if isinstance(val, dict) else val
            break

    if not raw_ranges:
        try:
            bot.edit_message_text(
                f'{get_emoji_tag("emj_cross")} <b>No live countries found for {escape_html(app_name)}.</b>',
                chat_id=chat_id, message_id=message_id, parse_mode="HTML"
            )
        except: pass
        return

    # Reference bot এর মতো: range → (flag, name), same country group করো
    country_buttons_map = {}  # "🇧🇩 Bangladesh" -> [rng1, rng2, ...]
    for rng in raw_ranges:
        rng_str = str(rng).strip()
        if not rng_str:
            continue
        flag, name = get_country_info(rng_str)
        if name == "Unknown":
            continue
        country_key = f"{flag} {name}"
        if country_key not in country_buttons_map:
            country_buttons_map[country_key] = []
        country_buttons_map[country_key].append(rng_str)

    if not country_buttons_map:
        try:
            bot.edit_message_text(
                f'{get_emoji_tag("emj_cross")} <b>No recognized countries for {escape_html(app_name)}.</b>',
                chat_id=chat_id, message_id=message_id, parse_mode="HTML"
            )
        except: pass
        return

    # Per-user session এ store করো — numeric index key (reference bot এর মতো)
    session = {"app": app_name, "countries": {}}
    for idx, (country_key, rng_list) in enumerate(country_buttons_map.items(), start=1):
        session["countries"][str(idx)] = {"label": country_key, "ranges": rng_list}
    _user_country_sessions[str(chat_id)] = session

    # Build buttons — callback: sel_cty|{idx}  (e.g. "sel_cty|3" = 9 bytes ✅)
    markup = InlineKeyboardMarkup(row_width=2)
    row = []
    for idx_str, info in session["countries"].items():
        label = info["label"]
        parts = label.split(" ", 1)
        country_name_part = parts[1] if len(parts) > 1 else label
        flag_emoji_id = get_premium_flag_id(country_name_part)
        # icon_custom_emoji_id তে premium flag, text এ শুধু country name (double flag এড়াতে)
        btn = ibtn(country_name_part, callback_data=f"sel_cty|{idx_str}",
                   style="danger", custom_emoji_id=flag_emoji_id if flag_emoji_id else get_emoji_id("emj_country"))
        row.append(btn)
        if len(row) == 2:
            markup.row(*row)
            row = []
    if row:
        markup.row(*row)
    markup.row(ibtn("« Back", callback_data="get_number", style="primary",
                    custom_emoji_id=get_emoji_id("emj_cross")))

    cnt = len(country_buttons_map)
    text = (f'🌎 <b>Select Country for {escape_html(app_name)}:</b>\n'
            f'━━━━━━━━━━━━━━━━━━━━━\n'
            f'<i>{cnt} live countries available</i>')
    try:
        msg = bot.edit_message_text(text, chat_id=chat_id, message_id=message_id,
                                    parse_mode="HTML", reply_markup=markup)
        save_active_menu(chat_id, msg)
    except:
        msg = bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)
        save_active_menu(chat_id, msg)


def show_services(chat_id, message_id=None):
    """Show live app buttons from API — auto GET NUMBER flow."""
    loading_text = f'{get_emoji_tag("emj_gen_number")} <b>⏳ Loading available apps...</b>'
    if message_id:
        try: bot.edit_message_text(loading_text, chat_id=chat_id, message_id=message_id, parse_mode="HTML")
        except: pass
    else:
        msg = bot.send_message(chat_id, loading_text, parse_mode="HTML")
        message_id = msg.message_id
    # Run fetch in background thread so bot stays responsive
    threading.Thread(target=_build_app_markup_and_send, args=(chat_id, message_id), daemon=True).start()

def show_countries(chat_id, srv_id, message_id=None):
    data = load_data()
    srv_data = data.get("services_data", {}).get(srv_id)
    if not srv_data: return
    
    markup = InlineKeyboardMarkup(row_width=2)
    for cnt_id, cnt in srv_data.get("countries", {}).items():
        if not isinstance(cnt, dict) or "name" not in cnt: continue
        cn_lower = str(cnt['name']).lower().strip()
        cnt_emoji_id = PREMIUM_FLAGS.get(cn_lower)
        if not cnt_emoji_id:
            for k, v in PREMIUM_FLAGS.items():
                if k in cn_lower:
                    cnt_emoji_id = v
                    break
        flag_symbol = get_unicode_flag(cnt['name'])
        
        # Display the country name with the premium emoji tag
        markup.add(ibtn(f"{flag_symbol} {cnt['name']}", callback_data=f"usr_c|{srv_id}|{cnt_id}", style="primary", custom_emoji_id=cnt_emoji_id))
        
    text = f'<b>Selected country for {srv_data.get("name", "Service")}:</b>'
    
    if message_id: 
        msg = bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, parse_mode="HTML", reply_markup=markup)
        save_active_menu(chat_id, msg)
    else: 
        msg = bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)
        save_active_menu(chat_id, msg)

# ============================================
# --- DYNAMIC INLINE KEYBOARD REBUILD ---
# ============================================
def get_updated_number_markup(chat_id):
    with active_sessions_lock:
        session = active_sessions.get(str(chat_id))
        if not session:
            return None
        
        numbers = session["numbers"]
        otp_status = session["otp_received"]
        wa_verified = session.get("wa_verified", set())
        srv_id = session["service_info"].get("srv_id", "custom")
        cnt_id = session["service_info"].get("cnt_id", "custom")
        custom_range = session["service_info"].get("custom_range")
        
        markup = InlineKeyboardMarkup(row_width=1)
        data = load_data()
        
        for num in numbers:
            is_done = otp_status.get(num, False)
            emoji_id = "5936067938955039275" if is_done else get_emoji_id("emj_copy_link")
            wa_badge = " ✅ WA Active" if num in wa_verified else ""
            markup.add(
                ibtn(f"= {num.lstrip('+')}{wa_badge}", copy_text_str=num, custom_emoji_id=emoji_id)
            )

        otp_group_url = data.get("texts", {}).get("otp_group_link", "https://t.me/rmmtzotpgroup")

        if srv_id and srv_id != "custom":
            # Row 1: Change Number + OTP Group on same line
            markup.row(
                ibtn("Change Number", callback_data=f"chg_r|{srv_id}|{cnt_id if not custom_range else 'custom'}", style="danger", custom_emoji_id=get_emoji_id("emj_changing")),
                ibtn("OTP Group", url=otp_group_url, style="primary", custom_emoji_id=get_emoji_id("emj_otp_group"))
            )
            # Row 2: Back to Country alone
            markup.row(
                ibtn("Back to Country", callback_data=f"usr_s|{srv_id}", style="success", custom_emoji_id=get_emoji_id("emj_country"))
            )
        else:
            callback_range = str(custom_range)[:40] if custom_range else "custom"
            auto_app_name = session["service_info"].get("auto_app_name", "")
            # Row 1: Change Number + OTP Group on same line
            markup.row(
                ibtn("Change Number", callback_data=f"chg_r|custom|{callback_range}", style="danger", custom_emoji_id=get_emoji_id("emj_changing")),
                ibtn("OTP Group", url=otp_group_url, style="primary", custom_emoji_id=get_emoji_id("emj_otp_group"))
            )
            # Row 2: Back to Country — if live API app, go back to that app's countries
            if auto_app_name:
                markup.row(
                    ibtn("Back to Country", callback_data="back_to_app_cty", style="success", custom_emoji_id=get_emoji_id("emj_country"))
                )
            else:
                markup.row(
                    ibtn("Back to Country", callback_data="back_to_services", style="success", custom_emoji_id=get_emoji_id("emj_country"))
                )

        return markup

# ============================================
# --- NUMBER FETCHING (ROUND-ROBIN RANGE) ---
# ============================================
# ============================================
# --- WHATSAPP NUMBER CHECKER ---
# ============================================
def check_whatsapp_number(phone, timeout=0.8):
    """
    Fast WhatsApp number checker (within 1 second).
    Returns (is_registered: bool, method: str)
    Fail-open: returns True on timeout/error so users are never blocked.
    """
    try:
        clean = re.sub(r'[^\d]', '', str(phone))
        if not clean or len(clean) < 7:
            return True, "skip"
        # Check via wa.me page content
        r = requests.get(
            f"https://wa.me/{clean}",
            timeout=timeout,
            allow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        )
        text = r.text.lower()
        # These phrases indicate the number is NOT on WhatsApp
        not_registered_signals = [
            "invalid phone number",
            "phone number is invalid",
            "number does not exist",
            "no longer exists",
            "cannot find this phone"
        ]
        if any(p in text for p in not_registered_signals):
            return False, "wa.me"
        # "api_button_send_message" appears only for valid WA accounts
        if "api_button_send_message" in text or "send message" in r.text.lower():
            return True, "wa.me"
        # Neutral / unknown response — fail-open
        return True, "unknown"
    except requests.exceptions.Timeout:
        return True, "timeout"
    except Exception:
        return True, "error"


def fetch_real_numbers(chat_id, srv_id, cnt_id, msg_id, custom_range=None, auto_app_name=None):
    data = load_data()
    api_key = data.get("api_key", NEXA_API_KEY)
    
    max_nums = data.get("settings", {}).get("max_numbers", 3)
    
    if srv_id and srv_id != "custom":
        srv_data = data.get("services_data", {}).get(srv_id)
        if not srv_data:
            bot.edit_message_text(f'{get_emoji_tag("emj_cross")} Service not found.', chat_id=chat_id, message_id=msg_id, parse_mode="HTML")
            return
        srv_name = srv_data.get('name', 'Service')
    else:
        srv_name = auto_app_name if auto_app_name else "Custom Number"

    if custom_range:
        ranges_list = [r.strip() for r in re.split(r'[,\s;]+', str(custom_range)) if r.strip()]
        detected_name, premium_flag = detect_country_by_prefix(ranges_list[0])
        display_name = auto_app_name if auto_app_name else detected_name
    else:
        cnt_data = srv_data.get("countries", {}).get(cnt_id) if srv_data else None
        if not cnt_data or not cnt_data.get("range"):
            bot.edit_message_text(f'{get_emoji_tag("emj_cross")} Out of stock / range config missing for this country.', chat_id=chat_id, message_id=msg_id, parse_mode="HTML")
            return
        ranges_list = [r.strip() for r in re.split(r'[,\s;]+', str(cnt_data["range"])) if r.strip()]
        display_name = cnt_data.get('name', 'Country')
        premium_flag = get_country_flag(display_name)

    if msg_id:
        try: bot.edit_message_text(f'{get_emoji_tag("emj_gen_number")} <b>Generating numbers... Please wait.</b>', chat_id=chat_id, message_id=msg_id, parse_mode="HTML")
        except: pass
    else:
        msg = bot.send_message(chat_id, f'{get_emoji_tag("emj_gen_number")} <b>Generating numbers... Please wait.</b>', parse_mode="HTML")
        msg_id = msg.message_id

    # --- Number Fetch Animation (background thread) ---
    _stop_anim = threading.Event()
    _anim_thread = threading.Thread(
        target=send_number_fetch_animation,
        args=(chat_id, msg_id, _stop_anim),
        daemon=True
    )
    _anim_thread.start()

    fetched_numbers = []
    wa_verified_numbers = set()   # tracks WhatsApp-verified numbers
    last_error_msg = "All ranges are currently out of stock."
    
    # --- Round-Robin Dynamic API Range Selector ---
    attempts = 0
    max_attempts = max_nums * len(ranges_list)
    range_index = 0
    
    api_key, base_url, panel = get_api_credentials()
    api_urls = get_api_urls(panel, base_url)
    api_headers = get_api_headers(panel, api_key)

    while len(fetched_numbers) < max_nums and attempts < max_attempts:
        raw_range = ranges_list[range_index % len(ranges_list)]
        range_index += 1
        attempts += 1

        try:
            # --- Panel-specific payload ---
            if panel in ("voltx_sms", "stex_sms"):
                rid_val = str(raw_range).replace("+", "").strip()
                payload = {"rid": rid_val}
            elif panel == "fastxotp":
                payload = {"range": raw_range, "is_national": False}
            else:  # zenex
                payload = {"range": raw_range, "is_national": False, "remove_plus": False}

            _resp = http_session.post(api_urls["getnum"], json=payload, headers=api_headers, timeout=10)
            res, _err = safe_json_parse(_resp)
            if _err:
                last_error_msg = _err
                continue
            if res is None:
                last_error_msg = "No response from API"
                continue

            # --- Universal number extractor ---
            num = None
            if isinstance(res, dict):
                d = res.get("data") or {}
                if isinstance(d, dict):
                    num = (d.get("full_number") or d.get("number") or
                           d.get("no_plus_number") or d.get("copy") or
                           d.get("phone") or d.get("mobile"))
                if not num and isinstance(d, list) and d:
                    num = (d[0].get("full_number") or d[0].get("number") or
                           d[0].get("no_plus_number") or d[0].get("copy") or
                           d[0].get("phone"))
                if not num:
                    num = (res.get("full_number") or res.get("number") or
                           res.get("no_plus_number") or res.get("copy") or
                           res.get("phone") or res.get("mobile"))
                if not num:
                    meta = res.get("meta") or {}
                    code = meta.get("code") or res.get("code") or res.get("status")
                    if str(code) not in ("200", "success", "ok", "true"):
                        last_error_msg = (meta.get("message") or res.get("message")
                                          or res.get("error") or str(res)[:200])
                    else:
                        last_error_msg = res.get("message") or "Empty number returned."
            elif isinstance(res, list) and res:
                first = res[0] if isinstance(res[0], dict) else {}
                num = first.get("full_number") or first.get("number") or first.get("phone")
            if num:
                fetched_num = f"+{str(num).replace('+', '')}"
                if fetched_num not in fetched_numbers:
                    # --- WhatsApp Active Check ---
                    is_wa_service = any(
                        wa in (auto_app_name or srv_name or "").lower()
                        for wa in ("whatsapp", "wa ", "wapp")
                    )
                    if is_wa_service:
                        wa_ok, _wa_method = check_whatsapp_number(fetched_num, timeout=0.8)
                        if not wa_ok:
                            last_error_msg = f"{fetched_num} not on WhatsApp — skipping"
                            continue
                        fetched_numbers.append(fetched_num)
                        wa_verified_numbers.add(fetched_num)
                    else:
                        fetched_numbers.append(fetched_num)
        except Exception as e:
            last_error_msg = f"Network Error: {str(e)}"

    # --- Stop the fetch animation ---
    _stop_anim.set()
    _anim_thread.join(timeout=0.3)

    if not fetched_numbers:
        if auto_app_name:
            back_cb = "back_to_services"
        elif srv_id and srv_id != "custom":
            back_cb = f"usr_s|{srv_id}"
        else:
            back_cb = "close_inline"
        markup = InlineKeyboardMarkup().add(
            ibtn("🔄 Try Again", callback_data=back_cb, style="danger", custom_emoji_id=get_emoji_id("emj_cross"))
        )
        error_text = f'{get_emoji_tag("emj_cross")} <b>Error: {escape_html(last_error_msg)}</b>'
        bot.edit_message_text(error_text, chat_id=chat_id, message_id=msg_id, parse_mode="HTML", reply_markup=markup)
        return

    text = (
        f"{get_emoji_tag('emj_done')} {premium_flag} <b>{escape_html(display_name)} Number selected</b>\n"
        f"{get_emoji_tag('emj_otp_coming')} <b>Waiting for OTP...</b>"
    )
    
    service_info = {
        "srv_name": srv_name,
        "cnt_name": display_name,
        "srv_id": srv_id if srv_id else "custom",
        "cnt_id": cnt_id if not custom_range else "custom",
        "custom_range": custom_range,
        "auto_app_name": auto_app_name
    }
    
    with active_sessions_lock:
        active_sessions[str(chat_id)] = {
            "msg_id": msg_id,
            "numbers": fetched_numbers,
            "otp_received": {num: False for num in fetched_numbers},
            "service_info": service_info,
            "wa_verified": wa_verified_numbers
        }
        
    markup = get_updated_number_markup(chat_id)
    bot.edit_message_text(text, chat_id=chat_id, message_id=msg_id, parse_mode="HTML", reply_markup=markup)
    
    active_polls[str(chat_id)] = True
    
    for num in fetched_numbers:
        threading.Thread(target=poll_otp_real, args=(chat_id, num, service_info, msg_id)).start()

# ============================================
# --- REAL OTP POLLING & FORWARDING ---
# ============================================
def poll_otp_real(chat_id, phone_number, service_info, msg_id):
    api_key, base_url, panel = get_api_credentials()
    api_urls = get_api_urls(panel, base_url)
    api_headers = get_api_headers(panel, api_key)
    timeout = 750
    start_time = time.time()
    target_num = str(phone_number).replace('+', '')
    
    while time.time() - start_time < timeout:
        if str(chat_id) not in active_polls or not active_polls[str(chat_id)]: return
        
        try:
            _resp = http_session.get(api_urls["otp"], headers=api_headers, timeout=10)
            res, _err = safe_json_parse(_resp)
            if _err or res is None:
                time.sleep(5)
                continue

            # --- Universal OTP list extractor ---
            otps_list = []
            if isinstance(res, dict):
                d = res.get("data")
                if isinstance(d, list):
                    otps_list = d
                elif isinstance(d, dict):
                    otps_list = d.get("otps") or d.get("active") or d.get("numbers") or []
                else:
                    otps_list = res.get("otps") or res.get("numbers") or res.get("sms") or []
            elif isinstance(res, list):
                otps_list = res

            for otp_entry in otps_list:
                entry_num = str(otp_entry.get("number", "")).replace('+', '')
                if entry_num != target_num:
                    continue

                # --- Panel-specific SMS field extraction ---
                if panel == "zenex":
                    full_sms = otp_entry.get("otp") or otp_entry.get("sms") or otp_entry.get("message") or ""
                elif panel == "fastxotp":
                    raw_otp = otp_entry.get("otp", "")
                    if raw_otp and str(raw_otp).strip().isdigit() and 3 <= len(str(raw_otp).strip()) <= 8:
                        full_sms = otp_entry.get("message") or otp_entry.get("sms") or f"OTP: {raw_otp}"
                    else:
                        full_sms = otp_entry.get("message") or otp_entry.get("sms") or str(raw_otp)
                else:
                    full_sms = str(otp_entry.get("message", ""))

                if not full_sms:
                    continue

                # --- Smart OTP code extraction ---
                otp_code = extract_otp(full_sms)
                if otp_code == "Not Extracted":
                    otp_code = "See Full SMS Below"

                # --- One-time balance credit ---
                num_key = f"{chat_id}_{target_num}"
                if num_key not in credited_numbers:
                    credited_numbers.add(num_key)
                    data = load_data()
                    current_bal = data.get("balances", {}).get(str(chat_id), 0.0)
                    bonus = data.get("settings", {}).get("otp_bonus", 0.001)
                    data.setdefault("balances", {})[str(chat_id)] = round(current_bal + bonus, 5)
                    leaderboard = data.setdefault("leaderboard", {"last_reset": time.time(), "stats": {}})
                    now = time.time()
                    reset_days = data.get("settings", {}).get("leaderboard_reset_days", 3)
                    try:
                        last_reset_time = float(leaderboard.get("last_reset", 0.0))
                    except:
                        last_reset_time = now
                        leaderboard["last_reset"] = now
                    if now - last_reset_time >= (reset_days * 86400):
                        leaderboard["stats"] = {}
                        leaderboard["last_reset"] = now
                    stats = leaderboard.setdefault("stats", {})
                    stats[str(chat_id)] = stats.get(str(chat_id), 0) + 1
                    save_data(data)
                else:
                    data = load_data()

                # --- Update session & markup ---
                with active_sessions_lock:
                    session = active_sessions.get(str(chat_id))
                    if session:
                        session["otp_received"][phone_number] = True
                updated_markup = get_updated_number_markup(chat_id)
                if updated_markup:
                    try:
                        bot.edit_message_reply_markup(chat_id, msg_id, reply_markup=updated_markup)
                    except: pass

                # --- Build OTP message ---
                premium_flag = get_country_premium_emoji(service_info['cnt_name'])
                short_code = get_country_short_code(service_info['cnt_name'])
                srv_emoji = get_service_emoji(service_info['srv_name'])
                masked = mask_number(phone_number)
                display_service = str(service_info['srv_name']).capitalize()
                formatted_message = (
                    f"<b>{escape_html(display_service)}</b>\n"
                    f"{premium_flag} <b>{escape_html(short_code)}</b> {srv_emoji} <code>{masked}</code>"
                )
                markup = InlineKeyboardMarkup(row_width=2)
                markup.add(ibtn(f" {otp_code}", copy_text_str=otp_code, style="success", custom_emoji_id=get_emoji_id("emj_key")))
                channel_url = data.get("texts", {}).get("main_channel_link", "https://t.me/MinoXofficial0")
                bot_url = f"https://t.me/{get_bot_username()}"
                markup.add(
                    ibtn(" CHANNEL", url=channel_url, style="danger", custom_emoji_id=get_emoji_id("emj_link")),
                    ibtn(" NUMBER", url=bot_url, style="primary", custom_emoji_id=get_emoji_id("emj_done"))
                )

                # --- Admin alert ---
                if data.get("settings", {}).get("admin_alerts", True) and not data.get("settings", {}).get("only_member_join_alert", True):
                    try:
                        bot.send_message(ADMIN_ID, f"🔔 <b>OTP Received!</b>\nUser: <code>{chat_id}</code>\nNumber: <code>{phone_number}</code>\nOTP: <code>{otp_code}</code>", parse_mode="HTML")
                    except: pass

                # --- OTP Animation ---
                send_otp_animation(chat_id)

                # --- Send to user & forward groups ---
                try:
                    bot.send_message(chat_id, formatted_message, parse_mode="HTML", reply_markup=markup)
                except: pass
                for grp in data.get("forward_groups", []):
                    try:
                        bot.send_message(grp, formatted_message, parse_mode="HTML", reply_markup=markup)
                    except: pass
                return
        except: pass
        time.sleep(4)

# ============================================
# --- STATIC MENUS & WALLET SYSTEM ---
# ============================================
def show_balance(chat_id, message_id=None):
    data = load_data()
    uid_str = str(chat_id)
    bal = data.get("balances", {}).get(uid_str, 0.0)
    min_wd = data.get("settings", {}).get("min_withdraw", 0.3)
    user_wallets = data.get("wallets", {}).get(uid_str, {})
    
    wallet_info = ""
    if user_wallets:
        wallet_info = f"\n{get_emoji_tag('emj_wallet')} <b>Your Saved Wallets:</b>\n"
        for w, v in user_wallets.items():
            wallet_info += f"- <b>{w.capitalize()}:</b> <code>{v}</code>\n"
    else:
        wallet_info = f"\n{get_emoji_tag('emj_wallet')} <i>No wallets added yet.</i>\n"

    text = f'{get_emoji_tag("emj_wallet")} <b>Balance</b>\n\n{get_emoji_tag("emj_wallet")} <b>Current balance:</b> {bal}$\n{get_emoji_tag("emj_stop")} <b>Minimum withdraw:</b> {min_wd}${wallet_info}\n<b>Choose a withdrawal method below:</b>'
    
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        ibtn("Bkash", callback_data="req_wd_bkash", style="success", custom_emoji_id=get_emoji_id("emj_bkash")), 
        ibtn("Nagad", callback_data="req_wd_nagad", style="success", custom_emoji_id=get_emoji_id("emj_nagad"))
    )
    markup.add(
        ibtn("Rocket", callback_data="req_wd_rocket", style="success", custom_emoji_id=get_emoji_id("emj_rocket")),
        ibtn("Binance", callback_data="req_wd_binance", style="success", custom_emoji_id=get_emoji_id("emj_binance"))
    )
    
    w_types = ["bkash", "nagad", "rocket", "binance"]
    for w in w_types:
        emoji_id = get_emoji_id(f"emj_{w}")
        if w in user_wallets:
            markup.add(
                ibtn(f"Edit {w.capitalize()}", callback_data=f"add_wal_{w}", style="primary", custom_emoji_id=emoji_id),
                ibtn(f"Delete {w.capitalize()}", callback_data=f"del_wal_{w}", style="danger", custom_emoji_id=get_emoji_id("emj_cross"))
            )
        else:
            markup.add(ibtn(f"Add {w.capitalize()}", callback_data=f"add_wal_{w}", style="primary", custom_emoji_id=emoji_id))
            
    markup.add(ibtn("Back to Menu", callback_data="close_inline", style="danger", custom_emoji_id=get_emoji_id("emj_cross")))
    
    if message_id: 
        msg = bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, parse_mode="HTML", reply_markup=markup)
        save_active_menu(chat_id, msg)
    else: 
        msg = bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)
        save_active_menu(chat_id, msg)

def process_add_wallet(message, wallet_type):
    chat_id = message.chat.id
    try: bot.delete_message(chat_id, message.message_id)
    except: pass
    
    if message.text and is_menu_button(message.text):
        bot.clear_step_handler_by_chat_id(chat_id)
        handle_text(message)
        return
    
    data = load_data()
    uid_str = str(chat_id)
    val = message.text.strip()
    data.setdefault("wallets", {}).setdefault(uid_str, {})[wallet_type] = val
    save_data(data)
    
    active_id = admin_active_menus.get(str(chat_id))
    show_profile(chat_id, active_id)

# ============================================
# --- SMART WITHDRAWAL SYSTEM ---
# ============================================
def process_smart_wallet_withdrawal(message, wallet_type, amount):
    chat_id = message.chat.id
    try: bot.delete_message(chat_id, message.message_id)
    except: pass
    
    if message.text and is_menu_button(message.text):
        bot.clear_step_handler_by_chat_id(chat_id)
        handle_text(message)
        return
        
    val = message.text.strip()
    data = load_data()
    uid_str = str(chat_id)
    
    data.setdefault("wallets", {}).setdefault(uid_str, {})[wallet_type] = val
    
    bal = data.get("balances", {}).get(uid_str, 0.0)
    if bal <= 0 or bal < amount:
        bot.send_message(chat_id, f"{get_emoji_tag('emj_cross')} <b>Error:</b> Balance changed or insufficient.", parse_mode="HTML")
        save_data(data)
        active_id = admin_active_menus.get(str(chat_id))
        show_profile(chat_id, active_id)
        return
        
    req_id = "wd_" + str(uuid.uuid4())[:8]
    data["balances"][uid_str] = round(bal - amount, 5) 
    data.setdefault("pending_withdrawals", {})[req_id] = {
        "uid": uid_str, 
        "amount": bal, 
        "method": wallet_type, 
        "address": val
    }
    save_data(data)
    
    bot.send_message(chat_id, f"{get_emoji_tag('emj_successful')} <b>Withdrawal Request Sent!</b>\n\n<b>Amount:</b> {bal}$\n<b>Method:</b> {wallet_type.capitalize()}\n<b>Address:</b> <code>{val}</code>\n\nPlease wait for admin approval.", parse_mode="HTML")
    
    admin_msg = (
        f"{get_emoji_tag('emj_wallet')} <b>NEW WITHDRAWAL REQUEST</b>\n\n"
        f"{get_emoji_tag('emj_profile')} <b>User ID:</b> <code>{uid_str}</code>\n"
        f"{get_emoji_tag('emj_wallet')} <b>Amount:</b> {bal}$\n"
        f"<b>Method:</b> {wallet_type.capitalize()}\n"
        f"<b>Address:</b> <code>{val}</code>"
    )
    amkup = InlineKeyboardMarkup(row_width=2)
    amkup.add(
        ibtn("APPROVE", callback_data=f"adm_wd_ok_{req_id}", style="success"), 
        ibtn("REJECT", callback_data=f"adm_wd_no_{req_id}", style="danger")
    )
    try:
        bot.send_message(ADMIN_ID, admin_msg, parse_mode="HTML", reply_markup=amkup)
    except: pass
    
    active_id = admin_active_menus.get(str(chat_id))
    show_profile(chat_id, active_id)

def show_referral(chat_id):
    data = load_data()
    uid_str = str(chat_id)
    bal = data.get("balances", {}).get(uid_str, 0.0)
    ref_bonus = data.get("settings", {}).get("ref_bonus", 0.01)
    
    ref_list = data.get("referrals", {}).get(uid_str, [])
    total_refs = len(ref_list)
    ref_earnings = round(total_refs * ref_bonus, 5)
    
    ref_link = f"https://t.me/{get_bot_username()}?start={chat_id}"
    text = (
        f'{get_emoji_tag("emj_refer")} <b>Refer & Earn</b>\n\n'
        f'{get_emoji_tag("emj_link")} <b>Your referral link:</b>\n'
        f'<code>{ref_link}</code>\n\n'
        f'{get_emoji_tag("emj_profile")} <b>Total referrals:</b> {total_refs}\n'
        f'{get_emoji_tag("emj_wallet")} <b>Referral earnings:</b> {ref_earnings}$\n'
        f'{get_emoji_tag("emj_add")} <b>Per referral:</b> {ref_bonus}$\n\n'
        f'{get_emoji_tag("emj_wallet")} <b>Your current balance:</b> {bal}$'
    )
    bot.send_message(chat_id, text, parse_mode="HTML")

def show_profile(chat_id, message_id=None):
    """Combined PROFILE = Balance + Referral info in one screen"""
    data = load_data()
    uid_str = str(chat_id)
    bal = data.get("balances", {}).get(uid_str, 0.0)
    min_wd = data.get("settings", {}).get("min_withdraw", 0.3)
    ref_bonus = data.get("settings", {}).get("ref_bonus", 0.01)
    otp_bonus = data.get("settings", {}).get("otp_bonus", 0.005)
    
    ref_list = data.get("referrals", {}).get(uid_str, [])
    total_refs = len(ref_list)
    ref_earnings = round(total_refs * ref_bonus, 5)
    
    ref_link = f"https://t.me/{get_bot_username()}?start={chat_id}"
    
    user_wallets = data.get("wallets", {}).get(uid_str, {})
    wallet_info = ""
    if user_wallets:
        wallet_info = f"\n{get_emoji_tag('emj_wallet')} <b>Saved Wallets:</b>\n"
        for w, v in user_wallets.items():
            wallet_info += f"  ▫️ <b>{w.capitalize()}:</b> <code>{v}</code>\n"
    
    # Build saved wallet info lines for display in text
    w_types = ["bkash", "nagad", "rocket", "binance"]
    wallet_lines = ""
    for w in w_types:
        if w in user_wallets:
            wallet_lines += f"  ▫️ <b>{w.capitalize()}:</b> <code>{user_wallets[w]}</code>\n"
    wallet_section = f"\n{get_emoji_tag('emj_wallet')} <b>Saved Numbers:</b>\n{wallet_lines}" if wallet_lines else ""

    text = (
        f"{get_emoji_tag('emj_profile')} <b>MY PROFILE</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{get_emoji_tag('emj_wallet')} <b>Balance:</b> <code>{bal}$</code>\n"
        f"{get_emoji_tag('emj_stop')} <b>Min Withdraw:</b> <code>{min_wd}$</code>\n"
        f"{get_emoji_tag('emj_key')} <b>OTP Bonus:</b> <code>{otp_bonus}$</code>/OTP\n"
        f"{wallet_section}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{get_emoji_tag('emj_refer')} <b>Referral Info</b>\n\n"
        f"{get_emoji_tag('emj_profile')} <b>Total Referrals:</b> <code>{total_refs}</code>\n"
        f"{get_emoji_tag('emj_wallet')} <b>Referral Earnings:</b> <code>{ref_earnings}$</code>\n"
        f"{get_emoji_tag('emj_add')} <b>Per Referral:</b> <code>{ref_bonus}$</code>\n\n"
        f"{get_emoji_tag('emj_link')} <b>Your Referral Link:</b>\n"
        f"<code>{ref_link}</code>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>Withdrawal Methods:</b>\n"
        f"<i>(Click a method to enter your number &amp; withdraw)</i>"
    )

    markup = InlineKeyboardMarkup(row_width=2)
    markup.row(
        ibtn("Bkash", callback_data="req_wd_bkash", style="success", custom_emoji_id=get_emoji_id("emj_bkash")),
        ibtn("Nagad", callback_data="req_wd_nagad", style="success", custom_emoji_id=get_emoji_id("emj_nagad"))
    )
    markup.row(
        ibtn("Rocket", callback_data="req_wd_rocket", style="success", custom_emoji_id=get_emoji_id("emj_rocket")),
        ibtn("Binance", callback_data="req_wd_binance", style="success", custom_emoji_id=get_emoji_id("emj_binance"))
    )
    markup.add(ibtn("Close", callback_data="close_inline", style="danger", custom_emoji_id=get_emoji_id("emj_cross")))
    
    if message_id:
        try:
            msg = bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, parse_mode="HTML", reply_markup=markup)
            save_active_menu(chat_id, msg)
        except:
            msg = bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)
            save_active_menu(chat_id, msg)
    else:
        msg = bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)
        save_active_menu(chat_id, msg)

def show_support(chat_id):
    data = load_data()
    texts = data.setdefault("texts", {})
    sup_text = texts.get("support", '<b>Support</b>\n\nClick the button below to contact support.')
    sup_lnk = texts.get("support_link", "https://t.me/rahi455")
    
    markup = InlineKeyboardMarkup(row_width=2).add(ibtn("Contact Support", url=sup_lnk, style="primary", custom_emoji_id=get_emoji_id("emj_support"))) 
    bot.send_message(chat_id, sup_text, parse_mode="HTML", reply_markup=markup)

def show_leaderboard(chat_id):
    data = load_data()
    leaderboard = data.setdefault("leaderboard", {"last_reset": time.time(), "stats": {}})
    
    now = time.time()
    try:
        last_reset_time = float(leaderboard.get("last_reset", 0.0))
    except:
        last_reset_time = now
        leaderboard["last_reset"] = now
        save_data(data)

    reset_days = data.get("settings", {}).get("leaderboard_reset_days", 3)
    reset_interval = reset_days * 86400

    if now - last_reset_time >= reset_interval:
        leaderboard["stats"] = {}
        leaderboard["last_reset"] = now
        save_data(data)
    
    stats = leaderboard.get("stats", {})
    sorted_stats = sorted(stats.items(), key=lambda item: item[1], reverse=True)[:10]
    
    text = f'{get_emoji_tag("emj_successful")} <b>DAILY TOP LEADERBOARD</b> {get_emoji_tag("emj_successful")}\n'
    text += f'<i>Resets automatically every {reset_days} days.</i>\n\n'
    
    if sorted_stats:
        for index, (uid, count) in enumerate(sorted_stats, 1):
            try:
                chat_info = bot.get_chat(int(uid))
                user_name = chat_info.first_name or chat_info.username or f"User ({uid[-4:]})"
            except:
                user_name = f"User ({uid[-4:]})"
            
            text += f'<b>{index}.</b> {escape_html(user_name)} ➜ <code>{count} OTPs</code>\n'
    else:
        text += f'<i>{get_emoji_tag("emj_stop")} No OTPs fetched in this reset cycle.</i>'
        
    bot.send_message(chat_id, text, parse_mode="HTML")

# ============================================
# --- ADMIN PANEL ---
# ============================================
def show_admin_panel(chat_id, message_id=None):
    if not is_admin(chat_id): return
    
    data = load_data()
    total_users = len(data.get("users", []))
    
    text = f'{get_emoji_tag("emj_admin_panel")} <b>POWERFUL ADMIN PANEL</b> {get_emoji_tag("emj_admin_panel")}\nManage your bot completely.\n\n{get_emoji_tag("emj_profile")} <b>Total Users:</b> <code>{total_users}</code>'
    
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        ibtn("MANAGE SERVICES", "admin_services", style="primary", custom_emoji_id=get_emoji_id("emj_admin_panel")), 
        ibtn("FORWARD GROUPS", "admin_groups", style="primary", custom_emoji_id=get_emoji_id("emj_support"))
    )
    markup.add(
        ibtn("SEARCH USER DATA", "admin_search_user", style="success", custom_emoji_id=get_emoji_id("emj_search")),  
        ibtn("MANAGE BALANCES", "admin_balance", style="success", custom_emoji_id=get_emoji_id("emj_wallet"))
    )
    markup.add(
        ibtn("BROADCAST", "admin_broadcast", style="primary", custom_emoji_id=get_emoji_id("emj_share")), 
        ibtn("BAN / UNBAN USER", "admin_ban", style="danger", custom_emoji_id=get_emoji_id("emj_ban"))
    )
    markup.add(
        ibtn("VIEW TOTAL USERS", "admin_users_count", style="primary", custom_emoji_id=get_emoji_id("emj_profile"))
    )
    markup.add(
        ibtn("MANAGE ADMINS", "admin_manage_admins", style="success", custom_emoji_id=get_emoji_id("emj_admin_panel")),
        ibtn("DESIGN & CONTROLS", "admin_texts", style="success", custom_emoji_id=get_emoji_id("emj_admin_panel"))
    )
    markup.add(
        ibtn("EXTRA FEATURES", "admin_extras", style="success", custom_emoji_id=get_emoji_id("emj_add"))
    )
    markup.add(
        ibtn("🔄 SWITCH PANEL", "admin_switch_panel", style="primary", custom_emoji_id=get_emoji_id("emj_changing"))
    )
    
    if message_id: 
        try:
            msg = bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, parse_mode="HTML", reply_markup=markup)
            save_active_menu(chat_id, msg)
        except: pass
    else: 
        msg = bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)
        save_active_menu(chat_id, msg)

def show_panel_switch_menu(chat_id, message_id=None):
    if not is_admin(chat_id): return
    data = load_data()
    panel_cfg = data.setdefault("panel_config", dict(PANEL_DEFAULTS))
    active = panel_cfg.get("active_panel", "voltx_sms")
    active_label = PANEL_LABELS.get(active, active)

    text = (
        f"{get_emoji_tag('emj_changing')} <b>SWITCH API PANEL</b>\n\n"
        f"▫️ <b>Active Panel:</b> <code>{active_label}</code>\n\n"
        f"Select a panel to switch to:"
    )
    markup = InlineKeyboardMarkup(row_width=1)
    for panel_id, label in PANEL_LABELS.items():
        style = "success" if panel_id == active else "primary"
        tick = "✅ " if panel_id == active else ""
        markup.add(ibtn(f"{tick}{label}", callback_data=f"set_panel|{panel_id}", style=style, custom_emoji_id=get_emoji_id("emj_changing")))
    markup.add(ibtn("SET API KEY", callback_data="admin_set_panel_key", style="danger", custom_emoji_id=get_emoji_id("emj_key")))
    markup.add(ibtn("BACK", callback_data="back_to_admin", style="danger", custom_emoji_id=get_emoji_id("emj_cross")))

    if message_id:
        try: msg = bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, parse_mode="HTML", reply_markup=markup); save_active_menu(chat_id, msg)
        except: pass
    else:
        msg = bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)
        save_active_menu(chat_id, msg)

def show_admin_services(chat_id, message_id=None):
    data = load_data()
    markup = InlineKeyboardMarkup(row_width=2)
    for srv_id, srv in data.get("services_data", {}).items(): 
        if not isinstance(srv, dict) or "name" not in srv: continue
        markup.add(ibtn(srv['name'], callback_data=f"adm_s|{srv_id}", style="primary"))
    markup.add(ibtn("ADD SERVICE", callback_data="add_srv", style="success", custom_emoji_id=get_emoji_id("emj_add")))
    markup.add(ibtn("BACK", callback_data="back_to_admin", style="danger", custom_emoji_id=get_emoji_id("emj_cross")))
    text = "<b>MANAGE SERVICES</b>\nSelect a service to view countries or manage."
    if message_id: 
        try:
            msg = bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, parse_mode="HTML", reply_markup=markup)
            save_active_menu(chat_id, msg)
        except: pass
    else: 
        msg = bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)
        save_active_menu(chat_id, msg)

def show_admin_countries(chat_id, srv_id, message_id=None):
    data = load_data()
    srv_data = data.get("services_data", {}).get(srv_id)
    if not srv_data: return
    
    markup = InlineKeyboardMarkup(row_width=2)
    for cnt_id, cnt in srv_data.get("countries", {}).items(): 
        if not isinstance(cnt, dict) or "name" not in cnt: continue
        rng = cnt.get("range", "Not Set")
        markup.add(ibtn(f"{cnt['name']} (Range: {rng})", callback_data=f"adm_c|{srv_id}|{cnt_id}", style="primary"))
        
    markup.add(ibtn("ADD COUNTRY & RANGE", callback_data=f"add_cnt|{srv_id}", style="success", custom_emoji_id=get_emoji_id("emj_add")))
    markup.add(
        ibtn("EDIT SERVICE NAME", callback_data=f"edit_srv|{srv_id}", style="primary", custom_emoji_id=get_emoji_id("emj_changing")),
        ibtn("DEL SERVICE", callback_data=f"del_srv|{srv_id}", style="danger", custom_emoji_id=get_emoji_id("emj_cross"))
    )
    markup.add(ibtn("BACK", callback_data="admin_services", style="danger", custom_emoji_id=get_emoji_id("emj_cross")))
    
    text = f"<b>COUNTRIES for {srv_data.get('name', 'Service')}</b>\nClick on any country to manage/edit name or range directly."
    if message_id: 
        try:
            msg = bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, parse_mode="HTML", reply_markup=markup)
            save_active_menu(chat_id, msg)
        except: pass
    else: 
        msg = bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)
        save_active_menu(chat_id, msg)

def show_admin_country_details(chat_id, srv_id, cnt_id, message_id=None):
    data = load_data()
    srv_data = data.get("services_data", {}).get(srv_id, {})
    cnt_data = srv_data.get("countries", {}).get(cnt_id) if isinstance(srv_data, dict) else None
    if not cnt_data: return
    
    text = f"<b>Country Details</b>\n\n{get_emoji_tag('emj_link')} <b>Service:</b> {srv_data.get('name', 'Service')}\n{get_emoji_tag('emj_country')} <b>Country Name:</b> {cnt_data.get('name', 'Country')}\n{get_emoji_tag('emj_number')} <b>API Range(s):</b> <code>{cnt_data.get('range', '')}</code>"
    
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        ibtn("Rename Country", callback_data=f"edit_cnt_name|{srv_id}|{cnt_id}", style="primary", custom_emoji_id=get_emoji_id("emj_changing")),
        ibtn("Manage Ranges", callback_data=f"manage_ranges|{srv_id}|{cnt_id}", style="primary", custom_emoji_id=get_emoji_id("emj_add"))
    )
    markup.add(ibtn("Delete Country", callback_data=f"del_cnt|{srv_id}|{cnt_id}", style="danger", custom_emoji_id=get_emoji_id("emj_cross")))
    markup.add(ibtn("Back", callback_data=f"adm_s|{srv_id}", style="primary", custom_emoji_id=get_emoji_id("emj_cross")))
    
    if message_id:
        try: 
            msg = bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, parse_mode="HTML", reply_markup=markup)
            save_active_menu(chat_id, msg)
        except: pass
    else:
        msg = bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)
        save_active_menu(chat_id, msg)

# --- STYLISH RANGE MANAGEMENT SCREEN ---
def show_manage_ranges(chat_id, srv_id, cnt_id, message_id=None):
    data = load_data()
    srv_data = data.get("services_data", {}).get(srv_id, {})
    cnt_data = srv_data.get("countries", {}).get(cnt_id) if isinstance(srv_data, dict) else None
    if not cnt_data: return
    
    ranges_str = cnt_data.get("range", "").strip()
    ranges_list = [r.strip() for r in ranges_str.split(",") if r.strip()]
    
    text = f"<b>🔧 Manage Ranges for {cnt_data.get('name')}</b>\n\n"
    if ranges_list:
        text += f"Current active ranges (Total: {len(ranges_list)}):\n"
        for idx, r in enumerate(ranges_list, 1):
            text += f"<b>{idx}.</b> <code>{r}</code>\n"
    else:
        text += "<i>No ranges configured yet.</i>"
        
    markup = InlineKeyboardMarkup(row_width=1)
    
    for idx, r in enumerate(ranges_list):
        markup.add(
            ibtn(f"❌ Delete {r}", callback_data=f"del_range_item|{srv_id}|{cnt_id}|{idx}", style="danger")
        )
        
    markup.add(
        ibtn("➕ Add New Range", callback_data=f"add_single_range|{srv_id}|{cnt_id}", style="success")
    )
    markup.add(
        ibtn("🔙 Back", callback_data=f"adm_c|{srv_id}|{cnt_id}", style="primary")
    )
    
    if message_id:
        try:
            msg = bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, parse_mode="HTML", reply_markup=markup)
            save_active_menu(chat_id, msg)
        except: pass
    else:
        msg = bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)
        save_active_menu(chat_id, msg)

# --- DYNAMIC FORWARD GROUPS SETTINGS SCREEN ---
def show_admin_forward_groups(chat_id, message_id=None):
    data = load_data()
    groups = data.setdefault("forward_groups", [])
    
    text = f"<b>📢 FORWARD GROUPS SETTINGS</b>\n\nAll successful OTP messages will be forwarded to these groups.\n\n"
    if groups:
        text += f"<b>Active Group Lists (Total: {len(groups)}):</b>\n"
        for idx, g in enumerate(groups, 1):
            text += f"<b>{idx}.</b> <code>{g}</code>\n"
    else:
        text += f"<i>No forward groups configured yet.</i>"
        
    markup = InlineKeyboardMarkup(row_width=1)
    
    for idx, g in enumerate(groups):
        markup.add(ibtn(f"❌ Delete {g}", callback_data=f"del_fwd_grp|{idx}", style="danger"))
        
    markup.add(
        ibtn("➕ Add Group ID(s)", callback_data="add_fwd_grp", style="success", custom_emoji_id=get_emoji_id("emj_add")),
        ibtn("🔙 BACK", callback_data="back_to_admin", style="primary", custom_emoji_id=get_emoji_id("emj_cross"))
    )
    
    if message_id:
        try: bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, parse_mode="HTML", reply_markup=markup)
        except: pass
    else:
        msg = bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)
        save_active_menu(chat_id, msg)

# --- Admin Panel Extra Controls ---
def show_admin_extras(chat_id, message_id=None):
    if not is_admin(chat_id): return
    data = load_data()
    m_mode = "ON" if data.get("maintenance_mode", False) else "OFF"
    alerts_on = "ON" if data.get("settings", {}).get("admin_alerts", True) else "OFF"
    alerts_type = "Only Member Join" if data.get("settings", {}).get("only_member_join_alert", True) else "All Alerts (Join + OTP)"
    
    text = (
        f"<b>⚙️ ADMIN EXTRA CONTROLS</b>\n\n"
        f"▫️ <b>Maintenance Mode:</b> <code>{m_mode}</code>\n"
        f"▫️ <b>Active OTP Polls:</b> <code>{len(active_sessions)}</code>\n"
        f"▫️ <b>Banned Users:</b> <code>{len(data.get('banned_users', []))}</code>\n"
        f"▫️ <b>Admin Alerts:</b> <code>{alerts_on}</code>\n"
        f"▫️ <b>Alert Type:</b> <code>{alerts_type}</code>"
    )
    
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        ibtn(f"Maint Mode: {m_mode}", callback_data="toggle_m_mode", style="primary"),
        ibtn("Set Maint Msg", callback_data="set_m_msg", style="primary")
    )
    markup.add(
        ibtn(f"Admin Alerts: {alerts_on}", callback_data="toggle_admin_alerts", style="success"),
        ibtn(f"Alert: {'Only Join' if data.get('settings', {}).get('only_member_join_alert', True) else 'All'}", callback_data="toggle_alert_type", style="success")
    )
    markup.add(
        ibtn("System Statistics", callback_data="sys_stats", style="primary"),
        ibtn("Manual Lboard Reset", callback_data="manual_lboard_reset", style="primary")
    )
    markup.add(
        ibtn("Database Backup", callback_data="db_backup", style="primary"),
        ibtn("OTP Broadcast", callback_data="otp_broadcast", style="primary")
    )
    markup.add(
        ibtn("List Banned Users", callback_data="list_banned", style="primary"),
        ibtn("Pending Withdrawals", callback_data="list_withdrawals", style="primary")
    )
    markup.add(
        ibtn("Clear Temp Files", callback_data="clear_temp", style="primary"),
        ibtn("Active Sessions", callback_data="active_sessions_count", style="primary")
    )
    
    # --- 3 NEW ESSENTIAL ADMIN FEATURES ---
    markup.add(
        ibtn("🔌 API Provider Bal", callback_data="adm_check_api_bal", style="success"),
        ibtn("📊 Export Users CSV", callback_data="adm_export_csv", style="success")
    )
    markup.add(
        ibtn("🧹 DB Optimizer", callback_data="adm_db_optimize", style="success"),
        ibtn("BACK", callback_data="back_to_admin", style="danger", custom_emoji_id=get_emoji_id("emj_cross"))
    )
    
    if message_id:
        try: bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, parse_mode="HTML", reply_markup=markup)
        except: pass
    else:
        bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)

# --- Admin actions ---
def process_add_srv(message):
    chat_id = message.chat.id
    try: bot.delete_message(chat_id, message.message_id)
    except: pass
    
    if message.text and is_menu_button(message.text):
        bot.clear_step_handler_by_chat_id(chat_id)
        handle_text(message)
        return
    
    data = load_data()
    srv_id = "s_" + str(uuid.uuid4())[:8]
    data.setdefault("services_data", {})[srv_id] = {"name": message.text.strip(), "countries": {}}
    save_data(data)
    
    active_id = admin_active_menus.get(str(chat_id))
    show_admin_services(chat_id, active_id)

def process_edit_srv(message, srv_id):
    chat_id = message.chat.id
    try: bot.delete_message(chat_id, message.message_id)
    except: pass
    
    if message.text and is_menu_button(message.text):
        bot.clear_step_handler_by_chat_id(chat_id)
        handle_text(message)
        return
    
    data = load_data()
    if srv_id in data.get("services_data", {}):
        data["services_data"][srv_id]["name"] = message.text.strip()
        save_data(data)
        
    active_id = admin_active_menus.get(str(chat_id))
    show_admin_countries(chat_id, srv_id, active_id)

def process_add_cnt_name(message, srv_id):
    chat_id = message.chat.id if hasattr(message, 'chat') else message.message.chat.id
    try: bot.delete_message(chat_id, message.message_id)
    except: pass
    
    if message.text and is_menu_button(message.text):
        bot.clear_step_handler_by_chat_id(chat_id)
        handle_text(message)
        return
    
    cnt_name = message.text.strip()
    active_id = admin_active_menus.get(str(chat_id))
    text = f"<b>Send Range for {escape_html(cnt_name)}:</b>\n<i>(Use comma to separate multiple ranges, e.g., 22507679, 22507678)</i>"
    markup = InlineKeyboardMarkup().add(ibtn("Cancel", callback_data=f"adm_s|{srv_id}", style="danger", custom_emoji_id=get_emoji_id("emj_cross")))
    
    if active_id:
        try: bot.edit_message_text(text, chat_id=chat_id, message_id=active_id, parse_mode="HTML", reply_markup=markup)
        except: pass
        
    bot.register_next_step_handler_by_chat_id(chat_id, process_add_cnt_range, srv_id, cnt_name)

def process_add_cnt_range(message, srv_id, cnt_name):
    chat_id = message.chat.id
    try: bot.delete_message(chat_id, message.message_id)
    except: pass
    
    if message.text and is_menu_button(message.text):
        bot.clear_step_handler_by_chat_id(chat_id)
        handle_text(message)
        return
    
    range_val = message.text.strip()
    data = load_data()
    cnt_id = "c_" + str(uuid.uuid4())[:8]
    data.setdefault("services_data", {}).setdefault(srv_id, {}).setdefault("countries", {})[cnt_id] = {
        "name": cnt_name,
        "range": range_val
    }
    save_data(data)
    
    active_id = admin_active_menus.get(str(chat_id))
    show_admin_countries(chat_id, srv_id, active_id)

def process_rename_country(message, srv_id, cnt_id):
    chat_id = message.chat.id
    try: bot.delete_message(chat_id, message.message_id)
    except: pass
    
    if message.text and is_menu_button(message.text):
        bot.clear_step_handler_by_chat_id(chat_id)
        handle_text(message)
        return
    
    new_name = message.text.strip()
    data = load_data()
    try:
        data["services_data"][srv_id]["countries"][cnt_id]["name"] = new_name
        save_data(data)
    except: pass
    
    active_id = admin_active_menus.get(str(chat_id))
    show_admin_country_details(chat_id, srv_id, cnt_id, active_id)

def process_add_single_range(message, srv_id, cnt_id):
    chat_id = message.chat.id
    try: bot.delete_message(chat_id, message.message_id)
    except: pass
    
    if message.text and is_menu_button(message.text):
        bot.clear_step_handler_by_chat_id(chat_id)
        handle_text(message)
        return
        
    new_range = message.text.strip().replace(",", "")
    if new_range:
        data = load_data()
        try:
            country_data = data["services_data"][srv_id]["countries"][cnt_id]
            old_range = country_data.get("range", "").strip()
            ranges_list = [r.strip() for r in old_range.split(",") if r.strip()]
            if new_range not in ranges_list:
                ranges_list.append(new_range)
            country_data["range"] = ", ".join(ranges_list)
            save_data(data)
        except:
            pass
            
    active_id = admin_active_menus.get(str(chat_id))
    show_manage_ranges(chat_id, srv_id, cnt_id, active_id)

def process_broadcast(message):
    chat_id = message.chat.id
    data = load_data()
    users = data.get("users", [])
    
    active_id = admin_active_menus.get(str(chat_id))
    if active_id:
        try: bot.edit_message_text("<b>Broadcast dispatch initiated... Please wait.</b>", chat_id=chat_id, message_id=active_id, parse_mode="HTML")
        except: pass
        
    success = 0
    failed = 0
    for user_id in users:
        try:
            bot.copy_message(chat_id=user_id, from_chat_id=chat_id, message_id=message.message_id)
            success += 1
        except:
            failed += 1
            
    try: bot.delete_message(chat_id, message.message_id)
    except: pass

    if active_id:
        text = f"{get_emoji_tag('emj_successful')} <b>Broadcast Completed!</b>\n\nSuccess: {success}\nFailed: {failed}"
        markup = InlineKeyboardMarkup().add(ibtn("Back", callback_data="back_to_admin", style="primary", custom_emoji_id=get_emoji_id("emj_cross")))
        try: bot.edit_message_text(text, chat_id=chat_id, message_id=active_id, parse_mode="HTML", reply_markup=markup)
        except: pass

def process_set_m_msg(message):
    chat_id = message.chat.id
    try: bot.delete_message(chat_id, message.message_id)
    except: pass
    
    if message.text and is_menu_button(message.text):
        bot.clear_step_handler_by_chat_id(chat_id)
        handle_text(message)
        return
        
    data = load_data()
    data["maintenance_message"] = message.text.strip()
    save_data(data)
    
    active_id = admin_active_menus.get(str(chat_id))
    show_admin_extras(chat_id, active_id)

def process_otp_broadcast(message):
    chat_id = message.chat.id
    try: bot.delete_message(chat_id, message.message_id)
    except: pass
    
    if message.text and is_menu_button(message.text):
        bot.clear_step_handler_by_chat_id(chat_id)
        handle_text(message)
        return
        
    data = load_data()
    groups = data.get("forward_groups", [])
    msg_text = message.text.strip()
    
    success = 0
    failed = 0
    for g in groups:
        try:
            bot.send_message(g, f"<b>📢 OTP BROADCAST</b>\n\n{escape_html(msg_text)}", parse_mode="HTML")
            success += 1
        except:
            failed += 1
            
    bot.send_message(chat_id, f"<b>Broadcast results:</b>\nSuccess: {success}\nFailed: {failed}", parse_mode="HTML")
    active_id = admin_active_menus.get(str(chat_id))
    show_admin_extras(chat_id, active_id)

def process_ban_user(message):
    chat_id = message.chat.id
    try: bot.delete_message(chat_id, message.message_id)
    except: pass
    
    if message.text and is_menu_button(message.text):
        bot.clear_step_handler_by_chat_id(chat_id)
        handle_text(message)
        return
    
    uid = message.text.strip()
    data = load_data()
    banned = data.setdefault("banned_users", [])
    
    if uid in banned:
        banned.remove(uid)
    else:
        banned.append(uid)
    save_data(data)
    
    active_id = admin_active_menus.get(str(chat_id))
    show_admin_panel(chat_id, active_id)

def process_add_admin(message):
    chat_id = message.chat.id
    try: bot.delete_message(chat_id, message.message_id)
    except: pass
    
    if message.text and is_menu_button(message.text):
        bot.clear_step_handler_by_chat_id(chat_id)
        handle_text(message)
        return
    
    try:
        new_admin = int(message.text.strip())
        data = load_data()
        admins = data.setdefault("admins", [ADMIN_ID])
        if new_admin not in admins:
            admins.append(new_admin)
            save_data(data)
    except: pass
    
    active_id = admin_active_menus.get(str(chat_id))
    show_admin_manage_admins_view(chat_id, active_id)

def process_remove_admin(message):
    chat_id = message.chat.id
    try: bot.delete_message(chat_id, message.message_id)
    except: pass
    
    if message.text and is_menu_button(message.text):
        bot.clear_step_handler_by_chat_id(chat_id)
        handle_text(message)
        return
    
    try:
        old_admin = int(message.text.strip())
        if old_admin != ADMIN_ID:
            data = load_data()
            admins = data.setdefault("admins", [ADMIN_ID])
            if old_admin in admins:
                admins.remove(old_admin)
                save_data(data)
    except: pass
    
    active_id = admin_active_menus.get(str(chat_id))
    show_admin_manage_admins_view(chat_id, active_id)

def process_add_group(message):
    chat_id = message.chat.id
    try: bot.delete_message(chat_id, message.message_id)
    except: pass
    
    if message.text and is_menu_button(message.text):
        bot.clear_step_handler_by_chat_id(chat_id)
        handle_text(message)
        return
    
    raw_text = message.text.strip()
    groups_to_add = [g.strip() for g in re.split(r'[,\s\n]+', raw_text) if g.strip()]
    
    data = load_data()
    fwd_groups = data.setdefault("forward_groups", [])
    added_count = 0
    for g in groups_to_add:
        if g not in fwd_groups:
            fwd_groups.append(g)
            added_count += 1
    save_data(data)
    
    bot.send_message(chat_id, f"✅ Successfully added {added_count} forward group(s)!")
    active_id = admin_active_menus.get(str(chat_id))
    show_admin_forward_groups(chat_id, active_id)

def process_search_user(message):
    chat_id = message.chat.id
    try: bot.delete_message(chat_id, message.message_id)
    except: pass
    
    if message.text and is_menu_button(message.text):
        bot.clear_step_handler_by_chat_id(chat_id)
        handle_text(message)
        return
    
    data = load_data()
    uid = message.text.strip()
    bal = data.get("balances", {}).get(uid, 0.0)
    wallets = data.get("wallets", {}).get(uid, {})
    status = "BANNED" if uid in data.get("banned_users", []) else "ACTIVE"
    
    text = f"{get_emoji_tag('emj_support')} <b>User Data for ID:</b> <code>{uid}</code>\n{get_emoji_tag('emj_profile')} <b>Status:</b> {status}\n\n{get_emoji_tag('emj_wallet')} <b>Balance:</b> {bal}$\n{get_emoji_tag('emj_wallet')} <b>Wallets:</b>\n"
    if wallets:
        for w, v in wallets.items(): text += f"- {w}: {v}\n"
    else: text += "- No wallets added.\n"
    
    markup = InlineKeyboardMarkup(row_width=2).add(ibtn("BACK", callback_data="back_to_admin", style="danger", custom_emoji_id=get_emoji_id("emj_cross")))
    active_id = admin_active_menus.get(str(chat_id))
    if active_id:
        try: bot.edit_message_text(text, chat_id=chat_id, message_id=active_id, parse_mode="HTML", reply_markup=markup)
        except: pass

def process_admin_balance_search(message):
    chat_id = message.chat.id
    try: bot.delete_message(chat_id, message.message_id)
    except: pass
    
    if message.text and is_menu_button(message.text):
        bot.clear_step_handler_by_chat_id(chat_id)
        handle_text(message)
        return
    
    uid = message.text.strip()
    data = load_data()
    active_id = admin_active_menus.get(str(chat_id))
    
    if uid not in data.get("users", []):
        text = f"{get_emoji_tag('emj_cross')} User not found in database."
        markup = InlineKeyboardMarkup().add(ibtn("BACK", callback_data="back_to_admin", style="primary", custom_emoji_id=get_emoji_id("emj_cross")))
        if active_id:
            try: bot.edit_message_text(text, chat_id=chat_id, message_id=active_id, parse_mode="HTML", reply_markup=markup)
            except: pass
        return
        
    bal = data.get("balances", {}).get(uid, 0.0)
    text = f"{get_emoji_tag('emj_profile')} <b>User:</b> <code>{uid}</code>\n{get_emoji_tag('emj_wallet')} <b>Current Balance:</b> {bal}$"
    
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        ibtn("ADD BALANCE", callback_data=f"adm_bal_add|{uid}", style="success", custom_emoji_id=get_emoji_id("emj_add")),
        ibtn("CUT BALANCE", callback_data=f"adm_bal_cut|{uid}", style="danger", custom_emoji_id=get_emoji_id("emj_cross"))
    )
    markup.add(ibtn("BACK", callback_data="back_to_admin", style="primary", custom_emoji_id=get_emoji_id("emj_cross")))
    
    if active_id:
        try: bot.edit_message_text(text, chat_id=chat_id, message_id=active_id, parse_mode="HTML", reply_markup=markup)
        except: pass

def process_add_bal(message, uid):
    chat_id = message.chat.id
    try: bot.delete_message(chat_id, message.message_id)
    except: pass
    
    if message.text and is_menu_button(message.text):
        bot.clear_step_handler_by_chat_id(chat_id)
        handle_text(message)
        return
    
    active_id = admin_active_menus.get(str(chat_id))
    try:
        amount = float(message.text.strip())
        data = load_data()
        curr = data.get("balances", {}).get(uid, 0.0)
        data.setdefault("balances", {})[uid] = round(curr + amount, 5)
        save_data(data)
        text = f"{get_emoji_tag('emj_successful')} Successfully added {amount}$ to {uid}. New balance: {data['balances'][uid]}$"
    except:
        text = f"{get_emoji_tag('emj_cross')} Invalid amount."
        
    markup = InlineKeyboardMarkup().add(ibtn("BACK", callback_data="back_to_admin", style="primary", custom_emoji_id=get_emoji_id("emj_cross")))
    if active_id:
        try: bot.edit_message_text(text, chat_id=chat_id, message_id=active_id, parse_mode="HTML", reply_markup=markup)
        except: pass

def process_cut_bal(message, uid):
    chat_id = message.chat.id
    try: bot.delete_message(chat_id, message.message_id)
    except: pass
    
    if message.text and is_menu_button(message.text):
        bot.clear_step_handler_by_chat_id(chat_id)
        handle_text(message)
        return
    
    active_id = admin_active_menus.get(str(chat_id))
    try:
        amount = float(message.text.strip())
        data = load_data()
        curr = data.get("balances", {}).get(uid, 0.0)
        new_bal = round(curr - amount, 5)
        if new_bal < 0: new_bal = 0.0
        data.setdefault("balances", {})[uid] = new_bal
        save_data(data)
        text = f"{get_emoji_tag('emj_successful')} Successfully deducted {amount}$ from {uid}. New balance: {data['balances'][uid]}$"
    except:
        text = f"{get_emoji_tag('emj_cross')} Invalid amount."
        
    markup = InlineKeyboardMarkup().add(ibtn("BACK", callback_data="back_to_admin", style="primary", custom_emoji_id=get_emoji_id("emj_cross")))
    if active_id:
        try: bot.edit_message_text(text, chat_id=chat_id, message_id=active_id, parse_mode="HTML", reply_markup=markup)
        except: pass

def _process_panel_key(message, panel_id):
    chat_id = message.chat.id
    try: bot.delete_message(chat_id, message.message_id)
    except: pass
    if not message.text or not message.text.strip():
        bot.send_message(chat_id, "❌ Invalid key. Try again.", parse_mode="HTML")
        return
    key_map = {
        "voltx_sms": "voltx_sms_api_key",
        "stex_sms": "stex_sms_api_key",
        "zenex": "zenex_api_key",
        "fastxotp": "fastxotp_api_key",
    }
    data = load_data()
    data.setdefault("panel_config", dict(PANEL_DEFAULTS))[key_map.get(panel_id, "voltx_sms_api_key")] = message.text.strip()
    save_data(data)
    label = PANEL_LABELS.get(panel_id, panel_id)
    bot.send_message(chat_id, f"{get_emoji_tag('emj_done')} <b>API key updated for {label}!</b>", parse_mode="HTML")
    active_id = admin_active_menus.get(str(chat_id))
    show_panel_switch_menu(chat_id, active_id)

def process_edit_api_key(message):
    chat_id = message.chat.id
    try: bot.delete_message(chat_id, message.message_id)
    except: pass
    
    if message.text and is_menu_button(message.text):
        bot.clear_step_handler_by_chat_id(chat_id)
        handle_text(message)
        return
    
    data = load_data()
    data["api_key"] = message.text.strip()
    save_data(data)
    
    active_id = admin_active_menus.get(str(chat_id))
    show_admin_panel(chat_id, active_id)

# ============================================
# --- ADMIN EDITABLE BOT TEXTS, DESIGN & SETTINGS ---
# ============================================
def show_admin_texts(chat_id, message_id=None):
    if not is_admin(chat_id): return
    text = "<b>BOT SETTINGS & DESIGN CONTROL</b>\n\nনিচের অপশনগুলো ব্যবহার করে বটের টেক্সট, বোতামের নাম, রেট এবং কাস্টম ইমোজি আইডি সম্পূর্ণ পরিবর্তন করতে পারবেন।"
    
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        ibtn("Bot Messages & Links", callback_data="adm_sub_msgs", style="primary"),
        ibtn("Main Menu Buttons Text", callback_data="adm_sub_btns", style="primary")
    )
    markup.add(
        ibtn("Rates & Limits Settings", callback_data="adm_sub_rates", style="primary"),
        ibtn("Custom Emoji Settings", callback_data="adm_sub_emojis", style="success")
    )
    markup.add(
        ibtn("Force Join Channels", callback_data="adm_sub_forcejoin", style="success"),
        ibtn("Back to Admin Panel", callback_data="back_to_admin", style="danger", custom_emoji_id=get_emoji_id("emj_cross"))
    )
    if message_id:
        try: 
            msg = bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, parse_mode="HTML", reply_markup=markup)
            save_active_menu(chat_id, msg)
        except: pass
    else:
        msg = bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)
        save_active_menu(chat_id, msg)

def show_sub_msgs(chat_id, message_id=None):
    data = load_data()
    texts = data.setdefault("texts", {})
    
    text = (
        f"{get_emoji_tag('emj_message')} <b>MESSAGES & LINKS</b>\n\n"
        f"<b>Welcome Text:</b>\n<i>{texts.get('welcome', '')}</i>\n\n"
        f"<b>Support Text:</b>\n<i>{texts.get('support', '')}</i>\n\n"
        f"<b>Support Link:</b> <code>{texts.get('support_link', '')}</code>\n"
        f"<b>OTP Group Link:</b> <code>{texts.get('otp_group_link', '')}</code>\n"
        f"<b>Main Channel Link:</b> <code>{texts.get('main_channel_link', '')}</code>\n"
        f"<b>Renge Group Link:</b> <code>{texts.get('renge_group_link', '')}</code>"
    )
    
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        ibtn("Welcome Msg", callback_data="edt_welcome", style="primary"),
        ibtn("Support Msg", callback_data="edt_support", style="primary")
    )
    markup.add(
        ibtn("Support Link", callback_data="edt_support_lnk", style="primary"),
        ibtn("OTP Group Link", callback_data="edt_otp_lnk", style="primary")
    )
    markup.add(
        ibtn("Main Channel Link", callback_data="edt_main_chan_lnk", style="primary"),
        ibtn("Renge Group Link", callback_data="edt_renge_grp_lnk", style="primary")
    )
    markup.add(ibtn("BACK", callback_data="admin_texts", style="danger", custom_emoji_id=get_emoji_id("emj_cross")))
    
    if message_id:
        try: 
            msg = bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, parse_mode="HTML", reply_markup=markup)
            save_active_menu(chat_id, msg)
        except: pass
    else:
        msg = bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)
        save_active_menu(chat_id, msg)

def show_sub_btns(chat_id, message_id=None):
    data = load_data()
    texts = data.setdefault("texts", {})
    
    text = (
        f"{get_emoji_tag('emj_changing')} <b>MAIN BUTTONS TEXT DESIGN</b>\n\n"
        f"<b>Get Number:</b> <code>{texts.get('btn_get_number', 'GET NUMBER')}</code>\n"
        f"<b>Balance:</b> <code>{texts.get('btn_balance', 'BALANCE')}</code>\n"
        f"<b>Refer:</b> <code>{texts.get('btn_refer', 'REFER AND EARN')}</code>\n"
        f"<b>Support:</b> <code>{texts.get('btn_support', 'SUPPORT')}</code>\n"
    )
    
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        ibtn("Get Num Btn", callback_data="edt_btn_get_num", style="primary"),
        ibtn("Balance Btn", callback_data="edt_btn_bal", style="primary")
    )
    markup.add(
        ibtn("Refer Btn", callback_data="edt_btn_ref", style="primary"),
        ibtn("Support Btn", callback_data="edt_btn_sup", style="primary")
    )
    markup.add(ibtn("BACK", callback_data="admin_texts", style="danger", custom_emoji_id=get_emoji_id("emj_cross")))
    
    if message_id:
        try: 
            msg = bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, parse_mode="HTML", reply_markup=markup)
            save_active_menu(chat_id, msg)
        except: pass
    else:
        msg = bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)
        save_active_menu(chat_id, msg)

def show_sub_rates(chat_id, message_id=None):
    data = load_data()
    settings = data.setdefault("settings", {})
    reset_days = settings.get("leaderboard_reset_days", 3)
    
    text = (
        f"{get_emoji_tag('emj_wallet')} <b>RATES & LIMITS SETTINGS</b>\n\n"
        f"<b>OTP Completion Bonus:</b> <code>{settings.get('otp_bonus', 0.001)}$</code>\n"
        f"<b>Referral Bonus:</b> <code>{settings.get('ref_bonus', 0.01)}$</code>\n"
        f"<b>Min Withdraw:</b> <code>{settings.get('min_withdraw', 0.3)}$</code>\n"
        f"<b>Max Numbers (Batch):</b> <code>{settings.get('max_numbers', 3)}</code>\n"
        f"<b>Lboard Reset Days:</b> <code>{reset_days} Days</code>"
    )
    
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        ibtn("OTP Bonus", callback_data="edt_otp_bon", style="primary"),
        ibtn("Ref Bonus", callback_data="edt_ref_bon", style="primary")
    )
    markup.add(
        ibtn("Min Withdraw", callback_data="edt_min_wd", style="primary"),
        ibtn("Max Numbers", callback_data="edt_max_nums", style="primary")
    )
    markup.add(
        ibtn("Lboard Reset Days", callback_data="edt_lboard_days", style="primary")
    )
    markup.add(ibtn("BACK", callback_data="admin_texts", style="danger", custom_emoji_id=get_emoji_id("emj_cross")))
    
    if message_id:
        try: 
            msg = bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, parse_mode="HTML", reply_markup=markup)
            save_active_menu(chat_id, msg)
        except: pass
    else:
        msg = bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)
        save_active_menu(chat_id, msg)

# --- Button Text Editing Handlers ---
def process_edit_btn_get_num(message):
    chat_id = message.chat.id
    try: bot.delete_message(chat_id, message.message_id)
    except: pass
    
    if message.text and is_menu_button(message.text):
        bot.clear_step_handler_by_chat_id(chat_id)
        handle_text(message)
        return
    
    data = load_data()
    data.setdefault("texts", {})["btn_get_number"] = message.text.strip()
    save_data(data)
    
    active_id = admin_active_menus.get(str(chat_id))
    show_sub_btns(chat_id, active_id)

def process_edit_btn_bal(message):
    chat_id = message.chat.id
    try: bot.delete_message(chat_id, message.message_id)
    except: pass
    
    if message.text and is_menu_button(message.text):
        bot.clear_step_handler_by_chat_id(chat_id)
        handle_text(message)
        return
    
    data = load_data()
    data.setdefault("texts", {})["btn_balance"] = message.text.strip()
    save_data(data)
    
    active_id = admin_active_menus.get(str(chat_id))
    show_sub_btns(chat_id, active_id)

def process_edit_btn_ref(message):
    chat_id = message.chat.id
    try: bot.delete_message(chat_id, message.message_id)
    except: pass
    
    if message.text and is_menu_button(message.text):
        bot.clear_step_handler_by_chat_id(chat_id)
        handle_text(message)
        return
    
    data = load_data()
    data.setdefault("texts", {})["btn_refer"] = message.text.strip()
    save_data(data)
    
    active_id = admin_active_menus.get(str(chat_id))
    show_sub_btns(chat_id, active_id)

def process_edit_btn_sup(message):
    chat_id = message.chat.id
    try: bot.delete_message(chat_id, message.message_id)
    except: pass
    
    if message.text and is_menu_button(message.text):
        bot.clear_step_handler_by_chat_id(chat_id)
        handle_text(message)
        return
    
    data = load_data()
    data.setdefault("texts", {})["btn_support"] = message.text.strip()
    save_data(data)
    
    active_id = admin_active_menus.get(str(chat_id))
    show_sub_btns(chat_id, active_id)

# --- Design & Msg Edits ---
def process_edit_welcome(message):
    chat_id = message.chat.id
    try: bot.delete_message(chat_id, message.message_id)
    except: pass
    
    if message.text and is_menu_button(message.text):
        bot.clear_step_handler_by_chat_id(chat_id)
        handle_text(message)
        return
    
    data = load_data()
    data.setdefault("texts", {})["welcome"] = message.text.strip()
    save_data(data)
    
    active_id = admin_active_menus.get(str(chat_id))
    show_sub_msgs(chat_id, active_id)

def process_edit_support(message):
    chat_id = message.chat.id
    try: bot.delete_message(chat_id, message.message_id)
    except: pass
    
    if message.text and is_menu_button(message.text):
        bot.clear_step_handler_by_chat_id(chat_id)
        handle_text(message)
        return
    
    data = load_data()
    data.setdefault("texts", {})["support"] = message.text.strip()
    save_data(data)
    
    active_id = admin_active_menus.get(str(chat_id))
    show_sub_msgs(chat_id, active_id)

def process_edit_support_link(message):
    chat_id = message.chat.id
    try: bot.delete_message(chat_id, message.message_id)
    except: pass
    
    if message.text and is_menu_button(message.text):
        bot.clear_step_handler_by_chat_id(chat_id)
        handle_text(message)
        return
    
    data = load_data()
    data.setdefault("texts", {})["support_link"] = message.text.strip()
    save_data(data)
    
    active_id = admin_active_menus.get(str(chat_id))
    show_sub_msgs(chat_id, active_id)

def process_edit_otp_link(message):
    chat_id = message.chat.id
    try: bot.delete_message(chat_id, message.message_id)
    except: pass
    
    if message.text and is_menu_button(message.text):
        bot.clear_step_handler_by_chat_id(chat_id)
        handle_text(message)
        return
    
    data = load_data()
    data.setdefault("texts", {})["otp_group_link"] = message.text.strip()
    save_data(data)
    
    active_id = admin_active_menus.get(str(chat_id))
    show_sub_msgs(chat_id, active_id)

def process_edit_main_chan_link(message):
    chat_id = message.chat.id
    try: bot.delete_message(chat_id, message.message_id)
    except: pass
    
    if message.text and is_menu_button(message.text):
        bot.clear_step_handler_by_chat_id(chat_id)
        handle_text(message)
        return
    
    data = load_data()
    data.setdefault("texts", {})["main_channel_link"] = message.text.strip()
    save_data(data)
    
    active_id = admin_active_menus.get(str(chat_id))
    show_sub_msgs(chat_id, active_id)

def process_edit_renge_grp_link(message):
    chat_id = message.chat.id
    try: bot.delete_message(chat_id, message.message_id)
    except: pass
    
    if message.text and is_menu_button(message.text):
        bot.clear_step_handler_by_chat_id(chat_id)
        handle_text(message)
        return
    
    data = load_data()
    data.setdefault("texts", {})["renge_group_link"] = message.text.strip()
    save_data(data)
    
    active_id = admin_active_menus.get(str(chat_id))
    show_sub_msgs(chat_id, active_id)

def process_edit_otp_bonus(message):
    chat_id = message.chat.id
    try: bot.delete_message(chat_id, message.message_id)
    except: pass
    
    if message.text and is_menu_button(message.text):
        bot.clear_step_handler_by_chat_id(chat_id)
        handle_text(message)
        return
    
    try:
        val = float(message.text.strip())
        data = load_data()
        data.setdefault("settings", {})["otp_bonus"] = val
        save_data(data)
    except: pass
    
    active_id = admin_active_menus.get(str(chat_id))
    show_sub_rates(chat_id, active_id)

def process_edit_ref_bonus(message):
    chat_id = message.chat.id
    try: bot.delete_message(chat_id, message.message_id)
    except: pass
    
    if message.text and is_menu_button(message.text):
        bot.clear_step_handler_by_chat_id(chat_id)
        handle_text(message)
        return
    
    try:
        val = float(message.text.strip())
        data = load_data()
        data.setdefault("settings", {})["ref_bonus"] = val
        save_data(data)
    except: pass
    
    active_id = admin_active_menus.get(str(chat_id))
    show_sub_rates(chat_id, active_id)

def process_edit_min_withdraw(message):
    chat_id = message.chat.id
    try: bot.delete_message(chat_id, message.message_id)
    except: pass
    
    if message.text and is_menu_button(message.text):
        bot.clear_step_handler_by_chat_id(chat_id)
        handle_text(message)
        return
    
    try:
        val = float(message.text.strip())
        data = load_data()
        data.setdefault("settings", {})["min_withdraw"] = val
        save_data(data)
    except: pass
    
    active_id = admin_active_menus.get(str(chat_id))
    show_sub_rates(chat_id, active_id)

def process_edit_max_numbers(message):
    chat_id = message.chat.id
    try: bot.delete_message(chat_id, message.message_id)
    except: pass
    
    if message.text and is_menu_button(message.text):
        bot.clear_step_handler_by_chat_id(chat_id)
        handle_text(message)
        return
    
    try:
        val = int(message.text.strip())
        data = load_data()
        data.setdefault("settings", {})["max_numbers"] = val
        save_data(data)
    except: pass
    
    active_id = admin_active_menus.get(str(chat_id))
    show_sub_rates(chat_id, active_id)

def process_edit_lboard_days(message):
    chat_id = message.chat.id
    try: bot.delete_message(chat_id, message.message_id)
    except: pass
    
    if message.text and is_menu_button(message.text):
        bot.clear_step_handler_by_chat_id(chat_id)
        handle_text(message)
        return
        
    try:
        val = int(message.text.strip())
        data = load_data()
        data.setdefault("settings", {})["leaderboard_reset_days"] = val
        save_data(data)
    except: pass
    
    active_id = admin_active_menus.get(str(chat_id))
    show_sub_rates(chat_id, active_id)

# ============================================
# --- DYNAMIC PREMIUM CUSTOM EMOJI PANEL ---
# ============================================
def show_sub_emojis_categories(chat_id, message_id=None):
    text = f"{get_emoji_tag('emj_successful')} <b>PREMIUM CUSTOM EMOJI SETTINGS</b>\n\nসিলেক্ট করুন কোন ক্যাটাগরির কাস্টম ইমোজি পরিবর্তন করতে চান:"
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        ibtn("Menu Buttons", callback_data="emj_cat_menu", style="primary"),
        ibtn("Admin Actions", callback_data="emj_cat_admin", style="primary")
    )
    markup.add(
        ibtn("Dynamic Statuses", callback_data="emj_cat_status", style="primary"),
        ibtn("Payment & Socials", callback_data="emj_cat_pay", style="primary")
    )
    markup.add(ibtn("BACK", callback_data="admin_texts", style="danger", custom_emoji_id=get_emoji_id("emj_cross")))
    if message_id:
        try: 
            msg = bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, parse_mode="HTML", reply_markup=markup)
            save_active_menu(chat_id, msg)
        except: pass
    else:
        msg = bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)
        save_active_menu(chat_id, msg)

def show_emojis_submenu(chat_id, keys, title, message_id=None):
    data = load_data()
    emojis = data.setdefault("custom_emojis", {})
    text = f"{get_emoji_tag('emj_successful')} <b>{title}</b>\n\n"
    for k in keys:
        text += f"- <b>{k.replace('emj_', '').upper()}:</b> <code>{emojis.get(k, 'Not Set')}</code>\n"
        
    markup = InlineKeyboardMarkup(row_width=2)
    for k in keys:
        markup.add(ibtn(k.replace('emj_', '').upper(), callback_data=f"edt_emj|{k}", style="primary"))
    markup.add(ibtn("BACK", callback_data="adm_sub_emojis", style="danger", custom_emoji_id=get_emoji_id("emj_cross")))
    
    if message_id: 
        msg = bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, parse_mode="HTML", reply_markup=markup)
        save_active_menu(chat_id, msg)
    else: 
        msg = bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)
        save_active_menu(chat_id, msg)

def process_edit_emoji(message, key):
    chat_id = message.chat.id
    try: bot.delete_message(chat_id, message.message_id)
    except: pass
    
    if message.text and is_menu_button(message.text):
        bot.clear_step_handler_by_chat_id(chat_id)
        handle_text(message)
        return
    
    val = message.text.strip()
    data = load_data()
    emojis = data.setdefault("custom_emojis", {})
    
    if val.lower() == 'clear':
        emojis[key] = ""
    elif val.isdigit() and len(val) >= 15:
        emojis[key] = val
        
    save_data(data)
    
    active_id = admin_active_menus.get(str(chat_id))
    show_sub_emojis_categories(chat_id, active_id)

# ============================================
# --- FORCE JOIN SETTINGS SYSTEM ---
# ============================================
def show_sub_forcejoin(chat_id, message_id=None):
    data = load_data()
    channels = data.setdefault("settings", {}).setdefault("force_join_channels", [])
    
    text = f"{get_emoji_tag('emj_broadcast')} <b>FORCE JOIN CHANNELS SETTINGS</b>\n\n"
    if channels:
        text += f"{get_emoji_tag('emj_link')} <b>Active Channel Lists:</b>\n"
        for idx, ch in enumerate(channels, 1):
            text += f"{idx}. <code>{ch}</code>\n"
    else:
        text += f"{get_emoji_tag('emj_stop')} <i>No active channels set currently.</i>"
        
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        ibtn("Add Channel", callback_data="add_fjc", style="success", custom_emoji_id=get_emoji_id("emj_add")),
        ibtn("Clear All", callback_data="clear_fjc", style="danger", custom_emoji_id=get_emoji_id("emj_cross"))
    )
    markup.add(ibtn("BACK", callback_data="admin_texts", style="primary", custom_emoji_id=get_emoji_id("emj_cross")))
    
    if message_id: 
        msg = bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, parse_mode="HTML", reply_markup=markup)
        save_active_menu(chat_id, msg)
    else: 
        msg = bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)
        save_active_menu(chat_id, msg)

def process_add_fjc(message):
    chat_id = message.chat.id
    try: bot.delete_message(chat_id, message.message_id)
    except: pass
    
    if message.text and is_menu_button(message.text):
        bot.clear_step_handler_by_chat_id(chat_id)
        handle_text(message)
        return
    
    val = message.text.strip()
    if val.startswith("@"):
        data = load_data()
        data.setdefault("settings", {}).setdefault("force_join_channels", []).append(val)
        save_data(data)
        
    active_id = admin_active_menus.get(str(chat_id))
    show_sub_forcejoin(chat_id, active_id)

# ============================================
# --- CUSTOM RANGE PREFIX STEP HANDLERS ---
# ============================================
def process_custom_rng_step_1(message, srv_id=None, edit_msg_id=None):
    chat_id = message.chat.id if hasattr(message, 'chat') else message.message.chat.id
    
    data = load_data()
    renge_link = data.get("texts", {}).get("renge_group_link", "https://t.me/newotppannel")
    
    text = (
        f"{get_emoji_tag('emj_changing')} <b>ENTER CUSTOM RANGE</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<blockquote>আপনার কাস্টম রেঞ্জ টাইপ করে পাঠান\n"
        f"(যেমন: 261387304XXX বা +236)</blockquote>"
    )
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        ibtn("View Range", url=renge_link, style="primary", custom_emoji_id=get_emoji_id("emj_link")),
        ibtn("Cancel", callback_data="cancel", style="danger", custom_emoji_id=get_emoji_id("emj_cross"))
    )
    
    if edit_msg_id:
        try: 
            msg = bot.edit_message_text(text, chat_id=chat_id, message_id=edit_msg_id, parse_mode="HTML", reply_markup=markup)
            save_active_menu(chat_id, msg)
        except:
            msg = bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)
            save_active_menu(chat_id, msg)
    else:
        msg = bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)
        save_active_menu(chat_id, msg)
        
    bot.register_next_step_handler_by_chat_id(chat_id, process_custom_rng_step_2, srv_id)

def process_custom_rng_step_2(message, srv_id=None):
    chat_id = message.chat.id
    
    if message.text and is_menu_button(message.text):
        bot.clear_step_handler_by_chat_id(chat_id)
        handle_text(message)
        return
        
    range_val = message.text.strip()
    try: bot.delete_message(chat_id, message.message_id)
    except: pass
    
    active_id = admin_active_menus.get(str(chat_id))
    if not range_val:
        if active_id:
            try: bot.edit_message_text(f"{get_emoji_tag('emj_cross')} Range cannot be empty.", chat_id=chat_id, message_id=active_id, parse_mode="HTML")
            except: pass
        return
        
    fetch_real_numbers(chat_id, srv_id, None, active_id, custom_range=range_val)

def show_admin_manage_admins_view(chat_id, message_id=None):
    data = load_data()
    admins = data.setdefault("admins", [ADMIN_ID])
    admin_list_str = "\n".join([f"- <code>{a}</code>" for a in admins])
    text = f"{get_emoji_tag('emj_admin_panel')} <b>Manage Bot Admins:</b>\n\nCurrent Admins:\n{admin_list_str}"
    markup = InlineKeyboardMarkup()
    markup.add(
        ibtn("Add Admin ID", callback_data="add_admin_id", style="success", custom_emoji_id=get_emoji_id("emj_add")),
        ibtn("Remove Admin ID", callback_data="remove_admin_id", style="danger", custom_emoji_id=get_emoji_id("emj_cross"))
    )
    markup.add(ibtn("BACK", callback_data="back_to_admin", style="primary", custom_emoji_id=get_emoji_id("emj_cross")))
    
    if message_id:
        try: 
            msg = bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, parse_mode="HTML", reply_markup=markup)
            save_active_menu(chat_id, msg)
        except: pass
    else:
        msg = bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)
        save_active_menu(chat_id, msg)

# ============================================
# --- 3 NEW ESSENTIAL ADMIN CONTROLLERS ---
# ============================================
def check_api_provider_balance(chat_id, message_id=None):
    api_key, base_url, panel = get_api_credentials()
    api_urls = get_api_urls(panel, base_url)
    api_headers = get_api_headers(panel, api_key)
    panel_label = PANEL_LABELS.get(panel, panel)

    text = f"{get_emoji_tag('emj_key')} <b>Checking Provider API Balance...</b>"
    if message_id:
        try: bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, parse_mode="HTML")
        except: pass
    else:
        msg = bot.send_message(chat_id, text, parse_mode="HTML")
        message_id = msg.message_id

    try:
        res = http_session.get(api_urls["balance"], headers=api_headers, timeout=10)
        if res.status_code == 200:
            res_json = res.json()
            data_part = res_json.get("data") or {}
            bal = data_part.get("balance") or data_part.get("credits") or res_json.get("balance") or "Unknown"
            cur = data_part.get("currency") or "USD"
            api_msg = (
                f"{get_emoji_tag('emj_successful')} <b>API PROVIDER STATUS</b>\n\n"
                f"▫️ <b>Active Panel:</b> <code>{panel_label}</code>\n"
                f"▫️ <b>Endpoint:</b> <code>{base_url}</code>\n"
                f"▫️ <b>API Balance:</b> <code>{bal} {cur}</code>\n"
                f"▫️ <b>API Key:</b> <code>{api_key[:4]}***{api_key[-3:] if len(api_key)>6 else ''}</code>\n"
                f"▫️ <b>Status Code:</b> <code>{res.status_code}</code>"
            )
        else:
            api_msg = (
                f"{get_emoji_tag('emj_cross')} <b>Provider API Balance Check Failed</b>\n\n"
                f"▫️ <b>Panel:</b> <code>{panel_label}</code>\n"
                f"▫️ <b>HTTP Status:</b> <code>{res.status_code}</code>\n"
                f"▫️ <b>Response:</b> <pre>{escape_html(res.text[:300])}</pre>"
            )
    except Exception as e:
        api_msg = f"{get_emoji_tag('emj_cross')} <b>Network Connection Error:</b>\n<code>{escape_html(str(e))}</code>"

    markup = InlineKeyboardMarkup().add(ibtn("BACK", callback_data="admin_extras", style="primary", custom_emoji_id=get_emoji_id("emj_cross")))
    try: bot.edit_message_text(api_msg, chat_id=chat_id, message_id=message_id, parse_mode="HTML", reply_markup=markup)
    except: pass

def export_users_csv(chat_id):
    data = load_data()
    users = data.get("users", [])
    if not users:
        bot.send_message(chat_id, "No users to export!", parse_mode="HTML")
        return
        
    file_path = "mino_users_database.csv"
    try:
        with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["User ID", "Balance ($)", "Saved Wallets", "Status"])
            for u in users:
                bal = data.get("balances", {}).get(u, 0.0)
                wallets_dict = data.get("wallets", {}).get(u, {})
                wallets_str = "; ".join([f"{k}: {v}" for k, v in wallets_dict.items()]) if wallets_dict else "None"
                status = "Banned" if u in data.get("banned_users", []) else "Active"
                writer.writerow([u, bal, wallets_str, status])
                
        with open(file_path, "rb") as f:
            bot.send_document(
                chat_id, f, 
                caption=f"📊 <b>Mino SMS Users Database Export</b>\n\n▫️ <b>Total Exported:</b> <code>{len(users)}</code> users\n▫️ <b>Format:</b> UTF-8 CSV Spreadsheet", 
                parse_mode="HTML"
            )
    except Exception as e:
        bot.send_message(chat_id, f"Error exporting CSV: {str(e)}")
    finally:
        if os.path.exists(file_path):
            try: os.remove(file_path)
            except: pass

def optimize_database_system(chat_id, message_id=None):
    data = load_data()
    
    # 1. Clear dead active polling sessions safely
    with active_sessions_lock:
        active_sessions.clear()
    active_polls.clear()
    
    # 2. Clear temp export files from directory
    cleared = 0
    for file in os.listdir("."):
        if (file.endswith(".txt") or file.endswith(".csv")) and (file.startswith("all_users") or file.startswith("mino_users_")):
            try:
                os.remove(file)
                cleared += 1
            except: pass
            
    # 3. Optimize data dictionary - prune old entries that are empty
    users = data.setdefault("users", [])
    balances = data.setdefault("balances", {})
    wallets = data.setdefault("wallets", {})
    
    for uid in list(balances.keys()):
        if uid not in users and int(uid) != ADMIN_ID:
            del balances[uid]
            
    save_data(data)
    
    opt_msg = (
        f"{get_emoji_tag('emj_successful')} <b>SYSTEM DATABASE OPTIMIZED</b>\n\n"
        f"▫️ <b>Active Polls Cleared:</b> <code>Yes</code>\n"
        f"▫️ <b>Temporary Files Deleted:</b> <code>{cleared}</code>\n"
        f"▫️ <b>Database Size Compacted:</b> <code>Success</code>\n"
        f"▫️ <b>Credits Memory Flushed:</b> <code>Completed</code>"
    )
    markup = InlineKeyboardMarkup().add(ibtn("BACK", callback_data="admin_extras", style="primary", custom_emoji_id=get_emoji_id("emj_cross")))
    if message_id:
        try: bot.edit_message_text(opt_msg, chat_id=chat_id, message_id=message_id, parse_mode="HTML", reply_markup=markup)
        except: pass
    else:
        bot.send_message(chat_id, opt_msg, parse_mode="HTML", reply_markup=markup)

# ============================================
# --- MESSAGE HANDLERS ---
# ============================================
@bot.message_handler(commands=['start', 'restart'])
def send_welcome(message):
    try:
        chat_id = message.chat.id
        if is_banned(chat_id): return
        
        data = load_data()
        if data.get("maintenance_mode", False) and not is_admin(chat_id):
            m_msg = data.get("maintenance_message", "<b>⚠️ System under maintenance. Please try again later.</b>")
            bot.send_message(chat_id, m_msg, parse_mode="HTML")
            return
            
        if not is_subscribed(chat_id):
            send_force_join(chat_id)
            return
            
        bot.clear_step_handler_by_chat_id(chat_id)
        active_polls.pop(str(chat_id), None)
        
        user_id_str = str(chat_id)
        
        command_parts = message.text.split()
        if len(command_parts) > 1 and user_id_str not in data.get("users", []):
            ref_id = command_parts[1].strip()
            if ref_id.isdigit() and ref_id != user_id_str:
                data.setdefault("referred_by", {})[user_id_str] = ref_id
                ref_bonus = data.get("settings", {}).get("ref_bonus", 0.01)
                
                data.setdefault("referrals", {})
                if ref_id not in data["referrals"]:
                    data["referrals"][ref_id] = []
                    
                if user_id_str not in data["referrals"][ref_id]:
                    data["referrals"][ref_id].append(user_id_str)
                    ref_bal = data.get("balances", {}).get(ref_id, 0.0)
                    data.setdefault("balances", {})[ref_id] = round(ref_bal + ref_bonus, 5)
                    try:
                        bot.send_message(ref_id, f"{get_emoji_tag('emj_successful')} <b>New Referral!</b>\nUser <a href='tg://user?id={user_id_str}'>{user_id_str}</a> has joined through your link.\nYou earned <b>{ref_bonus}$</b>!", parse_mode="HTML")
                    except: pass

        if user_id_str not in data.get("users", []):
            data.setdefault("users", []).append(user_id_str)
            # --- Admin Alert on New User Join ---
            if data.get("settings", {}).get("admin_alerts", True):
                try:
                    bot.send_message(ADMIN_ID, f"👤 <b>New User Started Bot!</b>\nID: <code>{user_id_str}</code>\nName: <a href='tg://user?id={user_id_str}'>{escape_html(message.from_user.first_name)}</a>", parse_mode="HTML")
                except:
                    pass
            
        save_data(data)
        
        welcome_text = data.get("texts", {}).get("welcome", '<tg-emoji emoji-id="5970074171449808121">🎁</tg-emoji> <b>╔══════════════════════╗</b>\n<b>         🤖 𝐑𝐌 𝐗𝐄𝐋 𝐁𝐎𝐓 🤖</b>\n<tg-emoji emoji-id="5970074171449808121">🎁</tg-emoji> <b>╚══════════════════════╝</b>\n\n<tg-emoji emoji-id="6237550015791765281">⭐</tg-emoji> <b>𝐔𝐋𝐓𝐑𝐀 𝐅𝐀𝐒𝐓 𝐎𝐓𝐏 𝐑𝐄𝐂𝐄𝐈𝐕𝐄𝐑</b> <tg-emoji emoji-id="6237550015791765281">⭐</tg-emoji>\n\n━━━━━━━━━━━━━━━━━━━━━━━━\n<tg-emoji emoji-id="6298670698948724690">✅</tg-emoji> <b>Instant OTP Delivery</b>\n<tg-emoji emoji-id="5296369303661067030">🔑</tg-emoji> <b>Premium Numbers Available</b>\n<tg-emoji emoji-id="5190899075968441286">💰</tg-emoji> <b>Earn Balance Per OTP</b>\n<tg-emoji emoji-id="5420396762189831222">🔗</tg-emoji> <b>Referral Bonus System</b>\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n<i>👇 Select an option from the menu below</i>')
        welcome_text += '<a href="https://t.me/rmxel1_bot?start=🤫">\u200b</a>'
        bot.send_message(chat_id, welcome_text, reply_markup=get_main_menu(chat_id), parse_mode="HTML")
    except Exception as e:
        try: bot.send_message(ADMIN_ID, f"Error in send_welcome: {str(e)}")
        except: pass

@bot.message_handler(commands=['admin'])
def command_admin(message):
    chat_id = message.chat.id
    if is_admin(chat_id):
        show_admin_panel(chat_id)

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    try:
        chat_id = message.chat.id
        if is_banned(chat_id): return
        
        data = load_data()
        if data.get("maintenance_mode", False) and not is_admin(chat_id):
            m_msg = data.get("maintenance_message", "<b>⚠️ System under maintenance. Please try again later.</b>")
            bot.send_message(chat_id, m_msg, parse_mode="HTML")
            return
            
        if not is_subscribed(chat_id):
            send_force_join(chat_id)
            return
            
        text = str(message.text).strip()
        bot.clear_step_handler_by_chat_id(chat_id)
        
        texts = data.setdefault("texts", {})
        btn_get_number = texts.get("btn_get_number", "GET NUMBER")
        btn_balance = texts.get("btn_balance", "BALANCE")
        btn_refer = texts.get("btn_refer", "REFER AND EARN")
        
        if text == btn_get_number: 
            show_services(chat_id)
        elif text == "Custom Number": 
            process_custom_rng_step_1(message)
        elif text == "PROFILE" or text == btn_balance or text == btn_refer:
            show_profile(chat_id)
        elif text == "LEADERBOARD": 
            show_leaderboard(chat_id)
        elif text == "ADMIN PANEL": 
            show_admin_panel(chat_id)
        elif text == "Renge Group":
            markup = InlineKeyboardMarkup().add(
                ibtn("Join Renge Group", url=data.get("texts", {}).get("renge_group_link", "https://t.me/newotppannel"), style="primary", custom_emoji_id=get_emoji_id("emj_link"))
            )
            bot.send_message(chat_id, f"{get_emoji_tag('emj_link')} <b>Click the button below to join our Renge Group:</b>", parse_mode="HTML", reply_markup=markup)
    except Exception as e:
        try: bot.send_message(ADMIN_ID, f"Error in handle_text for user {message.chat.id}: {str(e)}")
        except: pass

# ============================================
# --- CALLBACK HANDLERS ---
# ============================================
@bot.callback_query_handler(func=lambda call: True)
def handle_query(call):
    try:
        chat_id = call.message.chat.id
        msg_id = call.message.message_id
        if is_banned(chat_id): return
        
        data_call = call.data
        
        try: bot.answer_callback_query(call.id)
        except: pass
        
        bot.clear_step_handler_by_chat_id(chat_id)

        if data_call.startswith("cp_"):
            val = data_call.split("cp_")[1]
            bot.answer_callback_query(call.id, f"Copy: {val}", show_alert=True)

        elif data_call == "chk_joined":
            if is_subscribed(chat_id):
                bot.answer_callback_query(call.id, "Access Granted! Thanks for joining.", show_alert=True)
                try: bot.delete_message(chat_id, msg_id)
                except: pass
                data = load_data()
                welcome_text = data.get("texts", {}).get("welcome", '<tg-emoji emoji-id="5970074171449808121">🎁</tg-emoji> <b>╔══════════════════════╗</b>\n<b>         🤖 𝐑𝐌 𝐗𝐄𝐋 𝐁𝐎𝐓 🤖</b>\n<tg-emoji emoji-id="5970074171449808121">🎁</tg-emoji> <b>╚══════════════════════╝</b>\n\n<tg-emoji emoji-id="6237550015791765281">⭐</tg-emoji> <b>𝐔𝐋𝐓𝐑𝐀 𝐅𝐀𝐒𝐓 𝐎𝐓𝐏 𝐑𝐄𝐂𝐄𝐈𝐕𝐄𝐑</b> <tg-emoji emoji-id="6237550015791765281">⭐</tg-emoji>\n\n━━━━━━━━━━━━━━━━━━━━━━━━\n<tg-emoji emoji-id="6298670698948724690">✅</tg-emoji> <b>Instant OTP Delivery</b>\n<tg-emoji emoji-id="5296369303661067030">🔑</tg-emoji> <b>Premium Numbers Available</b>\n<tg-emoji emoji-id="5190899075968441286">💰</tg-emoji> <b>Earn Balance Per OTP</b>\n<tg-emoji emoji-id="5420396762189831222">🔗</tg-emoji> <b>Referral Bonus System</b>\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n<i>👇 Select an option from the menu below</i>') + '<a href="https://t.me/rmxel1_bot?start=🤫">\u200b</a>'
                bot.send_message(chat_id, welcome_text, reply_markup=get_main_menu(chat_id), parse_mode="HTML")
            else:
                bot.answer_callback_query(call.id, "You must join all channels first!", show_alert=True)

        elif data_call == "get_number": show_services(chat_id, msg_id)
        elif data_call == "back_to_services": show_services(chat_id, msg_id)
        elif data_call == "back_to_app_cty":
            session = _user_country_sessions.get(str(chat_id))
            if session and session.get("app"):
                show_app_ranges(chat_id, session["app"], msg_id)
            else:
                show_services(chat_id, msg_id)
        elif data_call == "show_profile_cb": show_profile(chat_id, msg_id)
        elif data_call == "open_custom_rng":
            try: bot.delete_message(chat_id, msg_id)
            except: pass
            import types
            fake_msg = types.SimpleNamespace(chat=types.SimpleNamespace(id=chat_id), message_id=msg_id, text="Custom Number", from_user=call.from_user)
            process_custom_rng_step_1(fake_msg)
        elif data_call == "retry_get_number":
            show_services(chat_id, message_id=msg_id)
        elif data_call.startswith("view_app_ranges|"):
            parts = data_call.split("|", 1)
            if len(parts) == 2:
                _, app_name = parts
                show_app_ranges(chat_id, app_name, msg_id)

        elif data_call.startswith("fetch_by_range|"):
            parts = data_call.split("|", 2)
            if len(parts) == 3:
                _, app_name, key_or_range = parts
                actual_range = _country_ranges_store.get(key_or_range, key_or_range)
                active_polls[str(chat_id)] = False
                fetch_real_numbers(chat_id, srv_id=None, cnt_id=None, msg_id=msg_id,
                                   custom_range=actual_range, auto_app_name=app_name)

        elif data_call.startswith("sel_cty|"):
            # Reference bot flow: country index দিয়ে per-user session থেকে ranges নাও
            idx_str = data_call.split("|", 1)[1]
            session = _user_country_sessions.get(str(chat_id))
            if not session:
                try:
                    bot.answer_callback_query(call.id, "⚠️ Session expired. Press GET NUMBER again.", show_alert=True)
                except: pass
                return
            cty_info = session.get("countries", {}).get(idx_str)
            if not cty_info:
                try:
                    bot.answer_callback_query(call.id, "⚠️ Country not found. Try again.", show_alert=True)
                except: pass
                return
            app_name = session.get("app", "")
            ranges_list = cty_info.get("ranges", [])
            actual_range = ",".join(ranges_list)
            active_polls[str(chat_id)] = False
            fetch_real_numbers(chat_id, srv_id=None, cnt_id=None, msg_id=msg_id,
                               custom_range=actual_range, auto_app_name=app_name)
        elif data_call == "close_inline":
            try: bot.delete_message(chat_id, msg_id)
            except: pass
            
        elif data_call == "cancel":
            bot.clear_step_handler_by_chat_id(chat_id)
            try: bot.delete_message(chat_id, msg_id)
            except: pass
            
        elif data_call.startswith("usr_s|"): show_countries(chat_id, data_call.split("|")[1], msg_id)
        elif data_call.startswith("usr_c|") or data_call.startswith("chg_r|"):
            active_polls[str(chat_id)] = False
            parts = data_call.split("|")
            
            if len(parts) > 1 and parts[1] == "custom":
                range_val = parts[2] if len(parts) > 2 else "custom"
                if range_val and range_val != "custom":
                    fetch_real_numbers(chat_id, srv_id=None, cnt_id=None, msg_id=msg_id, custom_range=range_val)
                else:
                    try: bot.delete_message(chat_id, msg_id)
                    except: pass
                    process_custom_rng_step_1(call.message)
            else:
                fetch_real_numbers(chat_id, parts[1], parts[2], msg_id)
                
        elif data_call.startswith("usr_custom_rng|"):
            srv_id = data_call.split("|")[1]
            process_custom_rng_step_1(call.message, srv_id, edit_msg_id=msg_id)

        # Wallet Callbacks
        elif data_call.startswith("add_wal_"):
            w_type = data_call.replace("add_wal_", "")
            active_id = admin_active_menus.get(str(chat_id))
            text = f"<b>Please send your {w_type.capitalize()} number/address:</b>"
            markup = InlineKeyboardMarkup().add(ibtn("Cancel", callback_data="cancel", style="danger", custom_emoji_id=get_emoji_id("emj_cross")))
            if active_id:
                try: bot.edit_message_text(text, chat_id=chat_id, message_id=active_id, parse_mode="HTML", reply_markup=markup)
                except: pass
            bot.register_next_step_handler_by_chat_id(chat_id, process_add_wallet, w_type)
        elif data_call.startswith("del_wal_"):
            w_type = data_call.replace("del_wal_", "")
            data = load_data()
            if str(chat_id) in data.get("wallets", {}) and w_type in data["wallets"][str(chat_id)]:
                del data["wallets"][str(chat_id)][w_type]
                save_data(data)
                bot.answer_callback_query(call.id, f"{w_type.capitalize()} wallet deleted!", show_alert=True)
                show_profile(chat_id, msg_id)
                
        # Withdrawal smart system handlers
        elif data_call.startswith("req_wd_"):
            w_type = data_call.replace("req_wd_", "")
            data = load_data()
            uid_str = str(chat_id)
            bal = data.get("balances", {}).get(uid_str, 0.0)
            min_wd = data.get("settings", {}).get("min_withdraw", 0.3)
            wallets = data.get("wallets", {}).get(uid_str, {})

            if bal <= 0 or bal < min_wd:
                # Can't answer_callback twice (already answered at top), use edit/send instead
                err_text = (
                    f"{get_emoji_tag('emj_cross')} <b>Insufficient Balance!</b>\n\n"
                    f"💰 <b>Your Balance:</b> <code>{bal}$</code>\n"
                    f"📌 <b>Minimum Withdraw:</b> <code>{min_wd}$</code>\n\n"
                    f"<i>Earn more balance to withdraw.</i>"
                )
                err_markup = InlineKeyboardMarkup().add(
                    ibtn("Back to Profile", callback_data="show_profile_cb", style="primary", custom_emoji_id=get_emoji_id("emj_profile")),
                    ibtn("Close", callback_data="close_inline", style="danger", custom_emoji_id=get_emoji_id("emj_cross"))
                )
                try:
                    bot.edit_message_text(err_text, chat_id=chat_id, message_id=msg_id, parse_mode="HTML", reply_markup=err_markup)
                except:
                    bot.send_message(chat_id, err_text, parse_mode="HTML", reply_markup=err_markup)
                return

            # Always ask for number — show saved number as hint if exists
            saved = wallets.get(w_type, "")
            hint = f"\n\n✅ <b>Previously saved:</b> <code>{saved}</code>\n<i>Send new number to update, or same to keep.</i>" if saved else ""
            text = (
                f"{get_emoji_tag(f'emj_{w_type}')} "
                f"<b>Enter your {w_type.capitalize()} number/address</b>\n\n"
                f"💰 <b>Withdraw Amount:</b> <code>{bal}$</code>{hint}"
            )
            markup = InlineKeyboardMarkup().add(
                ibtn("Cancel", callback_data="cancel", style="danger", custom_emoji_id=get_emoji_id("emj_cross"))
            )
            try:
                bot.edit_message_text(text, chat_id=chat_id, message_id=msg_id, parse_mode="HTML", reply_markup=markup)
                admin_active_menus[str(chat_id)] = msg_id
            except:
                sent = bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)
                admin_active_menus[str(chat_id)] = sent.message_id

            bot.register_next_step_handler_by_chat_id(chat_id, process_smart_wallet_withdrawal, w_type, bal)

        elif data_call.startswith("adm_wd_ok_"):
            req_id = data_call.replace("adm_wd_ok_", "")
            data = load_data()
            req = data.get("pending_withdrawals", {}).get(req_id)
            if req:
                approved_msg = (
                    f"{get_emoji_tag('emj_successful')} <b>WITHDRAWAL APPROVED!</b> {get_emoji_tag('emj_successful')}\n\n"
                    f"{get_emoji_tag('emj_wallet')} <b>Amount Sent:</b> {req['amount']}$\n"
                    f"<b>Method:</b> {req['method'].capitalize()}\n"
                    f"{get_emoji_tag('emj_link')} <b>Address:</b> <code>{req['address']}</code>\n\n"
                    f"<i>Your transaction has been executed successfully. Thank you for choosing us!</i>"
                )
                try: bot.send_message(req['uid'], approved_msg, parse_mode="HTML")
                except: pass
                del data["pending_withdrawals"][req_id]
                save_data(data)
                try: bot.edit_message_text(f"{call.message.text}\n\n{get_emoji_tag('emj_successful')} <b>APPROVED BY YOU</b>", chat_id=chat_id, message_id=msg_id, parse_mode="HTML")
                except: pass
                
        elif data_call.startswith("adm_wd_no_"):
            req_id = data_call.replace("adm_wd_no_", "")
            data = load_data()
            req = data.get("pending_withdrawals", {}).get(req_id)
            if req:
                curr = data.get("balances", {}).get(req['uid'], 0.0)
                data["balances"][req['uid']] = round(curr + req['amount'], 5)
                
                rejected_msg = (
                    f"{get_emoji_tag('emj_stop')} <b>WITHDRAWAL REJECTED</b>\n\n"
                    f"{get_emoji_tag('emj_wallet')} <b>Requested Amount:</b> {req['amount']}$\n"
                    f"<b>Method:</b> {req['method'].capitalize()}\n\n"
                    f"<i>Your withdrawal request was rejected by admin. The full amount has been refunded back to your bot balance.</i>"
                )
                try: bot.send_message(req['uid'], rejected_msg, parse_mode="HTML")
                except: pass
                del data["pending_withdrawals"][req_id]
                save_data(data)
                try: bot.edit_message_text(f"{call.message.text}\n\n{get_emoji_tag('emj_cross')} <b>REJECTED & REFUNDED</b>", chat_id=chat_id, message_id=msg_id, parse_mode="HTML")
                except: pass

        # Admin callbacks
        elif data_call == "back_to_admin": show_admin_panel(chat_id, msg_id)
        elif data_call == "admin_switch_panel": show_panel_switch_menu(chat_id, msg_id)
        elif data_call.startswith("set_panel|"):
            if is_admin(chat_id):
                new_panel = data_call.split("|", 1)[1]
                if new_panel in PANEL_LABELS:
                    data = load_data()
                    data.setdefault("panel_config", dict(PANEL_DEFAULTS))["active_panel"] = new_panel
                    save_data(data)
                    bot.answer_callback_query(call.id, f"✅ Switched to {PANEL_LABELS[new_panel]}", show_alert=True)
                    show_panel_switch_menu(chat_id, msg_id)
        elif data_call == "admin_set_panel_key":
            if is_admin(chat_id):
                data = load_data()
                panel_cfg = data.get("panel_config", PANEL_DEFAULTS)
                active = panel_cfg.get("active_panel", "voltx_sms")
                label = PANEL_LABELS.get(active, active)
                bot.send_message(chat_id, f"🔑 Send the new API key for <b>{label}</b>:", parse_mode="HTML")
                bot.register_next_step_handler_by_chat_id(chat_id, lambda m: _process_panel_key(m, active))
        elif data_call == "admin_services": show_admin_services(chat_id, msg_id)
        elif data_call == "admin_texts": show_admin_texts(chat_id, msg_id)
        elif data_call == "adm_sub_msgs": show_sub_msgs(chat_id, msg_id)
        elif data_call == "adm_sub_btns": show_sub_btns(chat_id, msg_id)
        elif data_call == "adm_sub_rates": show_sub_rates(chat_id, msg_id)
        
        elif data_call == "adm_sub_emojis": show_sub_emojis_categories(chat_id, msg_id)
        elif data_call == "emj_cat_menu":
            show_emojis_submenu(chat_id, ["emj_support", "emj_number", "emj_wallet", "emj_profile", "emj_refer", "emj_admin_panel", "emj_key", "emj_search", "emj_share"], "Menu Buttons Custom Emojis", msg_id)
        elif data_call == "emj_cat_admin":
            show_emojis_submenu(chat_id, ["emj_ban", "emj_broadcast", "emj_add"], "Admin Panel Actions Custom Emojis", msg_id)
        elif data_call == "emj_cat_status":
            show_emojis_submenu(chat_id, ["emj_otp_coming", "emj_otp_received", "emj_message", "emj_stop", "emj_successful", "emj_changing", "emj_link", "emj_country", "emj_done", "emj_gen_number", "emj_copy_link"], "Dynamic Status Messages Custom Emojis", msg_id)
        elif data_call == "emj_cat_pay":
            show_emojis_submenu(chat_id, ["emj_bkash", "emj_rocket", "emj_binance", "emj_instagram", "emj_facebook", "emj_tiktok", "emj_whatsapp", "emj_telegram", "emj_nagad", "emj_cross", "emj_otp_group"], "Payments & Service Custom Emojis", msg_id)
        
        elif data_call.startswith("edt_emj|"):
            key = data_call.split("|")[1]
            data = load_data()
            old_val = data.setdefault("custom_emojis", {}).get(key, "Not Set")
            active_id = admin_active_menus.get(str(chat_id))
            text = f"📌 <b>Current Saved Custom Emoji ID for {key}:</b> <code>{old_val}</code>\n\n💬 Send the new 15-20 digit Custom Emoji ID:\n(Or send <code>clear</code> to remove it)"
            markup = InlineKeyboardMarkup().add(ibtn("Cancel", callback_data="adm_sub_emojis", style="danger", custom_emoji_id=get_emoji_id("emj_cross")))
            if active_id:
                try: bot.edit_message_text(text, chat_id=chat_id, message_id=active_id, parse_mode="HTML", reply_markup=markup)
                except: pass
            bot.register_next_step_handler_by_chat_id(chat_id, process_edit_emoji, key)
        
        elif data_call == "adm_sub_forcejoin": show_sub_forcejoin(chat_id, msg_id)
        elif data_call == "add_fjc":
            active_id = admin_active_menus.get(str(chat_id))
            text = "📢 <b>Send Channel Username (must start with @, e.g. <code>@ChannelName</code>):</b>"
            markup = InlineKeyboardMarkup().add(ibtn("Cancel", callback_data="adm_sub_forcejoin", style="danger", custom_emoji_id=get_emoji_id("emj_cross")))
            if active_id:
                try: bot.edit_message_text(text, chat_id=chat_id, message_id=active_id, parse_mode="HTML", reply_markup=markup)
                except: pass
            bot.register_next_step_handler_by_chat_id(chat_id, process_add_fjc)
        elif data_call == "clear_fjc":
            data = load_data()
            data.setdefault("settings", {})["force_join_channels"] = []
            save_data(data)
            bot.answer_callback_query(call.id, "Force Join channels cleared!", show_alert=True)
            show_sub_forcejoin(chat_id, msg_id)

        elif data_call == "admin_broadcast":
            active_id = admin_active_menus.get(str(chat_id))
            text = "📢 <b>Send the message (Text, Photo, Video) you want to broadcast:</b>"
            markup = InlineKeyboardMarkup().add(ibtn("Cancel", callback_data="back_to_admin", style="danger", custom_emoji_id=get_emoji_id("emj_cross")))
            if active_id:
                try: bot.edit_message_text(text, chat_id=chat_id, message_id=active_id, parse_mode="HTML", reply_markup=markup)
                except: pass
            bot.register_next_step_handler_by_chat_id(chat_id, process_broadcast)
        elif data_call == "admin_ban":
            active_id = admin_active_menus.get(str(chat_id))
            text = f"<b>Send User ID to BAN or UNBAN:</b>\n(If user is already banned, they will be unbanned)"
            markup = InlineKeyboardMarkup().add(ibtn("Cancel", callback_data="back_to_admin", style="danger", custom_emoji_id=get_emoji_id("emj_cross")))
            if active_id:
                try: bot.edit_message_text(text, chat_id=chat_id, message_id=active_id, parse_mode="HTML", reply_markup=markup)
                except: pass
            bot.register_next_step_handler_by_chat_id(chat_id, process_ban_user)
        elif data_call == "admin_api":
            data = load_data()
            old_api = data.get("api_key", NEXA_API_KEY)
            active_id = admin_active_menus.get(str(chat_id))
            text = f"📌 <b>Current API Key:</b> <code>{old_api}</code>\n\n🔑 Send your new NEXA API Key below:"
            markup = InlineKeyboardMarkup().add(ibtn("Cancel", callback_data="back_to_admin", style="danger", custom_emoji_id=get_emoji_id("emj_cross")))
            if active_id:
                try: bot.edit_message_text(text, chat_id=chat_id, message_id=active_id, parse_mode="HTML", reply_markup=markup)
                except: pass
            bot.register_next_step_handler_by_chat_id(chat_id, process_edit_api_key)

        elif data_call == "add_srv":
            active_id = admin_active_menus.get(str(chat_id))
            text = "✏️ <b>Send Service Name:</b>"
            markup = InlineKeyboardMarkup().add(ibtn("Cancel", callback_data="admin_services", style="danger", custom_emoji_id=get_emoji_id("emj_cross")))
            if active_id:
                try: bot.edit_message_text(text, chat_id=chat_id, message_id=active_id, parse_mode="HTML", reply_markup=markup)
                except: pass
            bot.register_next_step_handler_by_chat_id(chat_id, process_add_srv)
        elif data_call.startswith("adm_s|"): show_admin_countries(chat_id, data_call.split("|")[1], msg_id)
        elif data_call.startswith("add_cnt|"):
            srv_id = data_call.split("|")[1]
            active_id = admin_active_menus.get(str(chat_id))
            text = "🌍 <b>Send Country Name:</b>"
            markup = InlineKeyboardMarkup().add(ibtn("Cancel", callback_data=f"adm_s|{srv_id}", style="danger", custom_emoji_id=get_emoji_id("emj_cross")))
            if active_id:
                try: bot.edit_message_text(text, chat_id=chat_id, message_id=active_id, parse_mode="HTML", reply_markup=markup)
                except: pass
            bot.register_next_step_handler_by_chat_id(chat_id, process_add_cnt_name, srv_id)
        elif data_call.startswith("adm_c|"): 
            show_admin_country_details(chat_id, data_call.split("|")[1], data_call.split("|")[2], msg_id)
            
        elif data_call.startswith("edit_srv|"):
            srv_id = data_call.split("|")[1]
            data = load_data()
            old_srv = data.setdefault("services_data", {}).get(srv_id, {}).get("name", "Unknown")
            active_id = admin_active_menus.get(str(chat_id))
            text = f"📌 <b>Current Service Name:</b> <code>{old_srv}</code>\n\n✏️ <b>Send new name for this Service:</b>"
            markup = InlineKeyboardMarkup().add(ibtn("Cancel", callback_data=f"adm_s|{srv_id}", style="danger", custom_emoji_id=get_emoji_id("emj_cross")))
            if active_id:
                try: bot.edit_message_text(text, chat_id=chat_id, message_id=active_id, parse_mode="HTML", reply_markup=markup)
                except: pass
            bot.register_next_step_handler_by_chat_id(chat_id, process_edit_srv, srv_id)
        elif data_call.startswith("del_srv|"):
            srv_id = data_call.split("|")[1]
            db = load_data()
            if srv_id in db.get("services_data", {}):
                del db["services_data"][srv_id]
                save_data(db)
            show_admin_services(chat_id, msg_id)
            
        elif data_call.startswith("edit_cnt_name|"):
            _, srv_id, cnt_id = data_call.split("|")
            data = load_data()
            old_cnt_name = data.setdefault("services_data", {}).get(srv_id, {}).get("countries", {}).get(cnt_id, {}).get("name", "Unknown")
            active_id = admin_active_menus.get(str(chat_id))
            text = f"📌 <b>Current Country Name:</b> <code>{old_cnt_name}</code>\n\n✏️ <b>Send new Name for this Country:</b>"
            markup = InlineKeyboardMarkup().add(ibtn("Cancel", callback_data=f"adm_c|{srv_id}|{cnt_id}", style="danger", custom_emoji_id=get_emoji_id("emj_cross")))
            if active_id:
                try: bot.edit_message_text(text, chat_id=chat_id, message_id=active_id, parse_mode="HTML", reply_markup=markup)
                except: pass
            bot.register_next_step_handler_by_chat_id(chat_id, process_rename_country, srv_id, cnt_id)

        # Range management screen callbacks
        elif data_call.startswith("manage_ranges|"):
            _, srv_id, cnt_id = data_call.split("|")
            show_manage_ranges(chat_id, srv_id, cnt_id, msg_id)
            
        elif data_call.startswith("del_range_item|"):
            _, srv_id, cnt_id, idx_str = data_call.split("|")
            idx = int(idx_str)
            data = load_data()
            try:
                country_data = data["services_data"][srv_id]["countries"][cnt_id]
                old_range = country_data.get("range", "").strip()
                ranges_list = [r.strip() for r in old_range.split(",") if r.strip()]
                if 0 <= idx < len(ranges_list):
                    del ranges_list[idx]
                country_data["range"] = ", ".join(ranges_list)
                save_data(data)
                bot.answer_callback_query(call.id, "Range deleted!", show_alert=True)
            except:
                pass
            show_manage_ranges(chat_id, srv_id, cnt_id, msg_id)
            
        elif data_call.startswith("add_single_range|"):
            _, srv_id, cnt_id = data_call.split("|")
            active_id = admin_active_menus.get(str(chat_id))
            text = "✏️ <b>Send the new single API range to add (Do not use commas):</b>"
            markup = InlineKeyboardMarkup().add(ibtn("Cancel", callback_data=f"manage_ranges|{srv_id}|{cnt_id}", style="danger"))
            if active_id:
                try: bot.edit_message_text(text, chat_id=chat_id, message_id=active_id, parse_mode="HTML", reply_markup=markup)
                except: pass
            bot.register_next_step_handler_by_chat_id(chat_id, process_add_single_range, srv_id, cnt_id)
            
        elif data_call.startswith("del_cnt|"):
            _, srv_id, cnt_id = data_call.split("|")
            db = load_data()
            try:
                del db["services_data"][srv_id]["countries"][cnt_id]
                save_data(db)
                bot.answer_callback_query(call.id, "Country Deleted!", show_alert=True)
            except: pass
            show_admin_countries(chat_id, srv_id, msg_id)

        elif data_call == "edt_welcome":
            data = load_data()
            old_val = data.setdefault("texts", {}).get("welcome", "")
            active_id = admin_active_menus.get(str(chat_id))
            text = f"📌 <b>Current Welcome Message:</b>\n<pre>{old_val}</pre>\n\n✏️ <b>Send new Welcome Text (Markdown/HTML supported):</b>"
            markup = InlineKeyboardMarkup().add(ibtn("Cancel", callback_data="adm_sub_msgs", style="danger", custom_emoji_id=get_emoji_id("emj_cross")))
            if active_id:
                try: bot.edit_message_text(text, chat_id=chat_id, message_id=active_id, parse_mode="HTML", reply_markup=markup)
                except: pass
            bot.register_next_step_handler_by_chat_id(chat_id, process_edit_welcome)
        elif data_call == "edt_support":
            data = load_data()
            old_val = data.setdefault("texts", {}).get("support", "")
            active_id = admin_active_menus.get(str(chat_id))
            text = f"📌 <b>Current Support Message:</b>\n<pre>{old_val}</pre>\n\n✏️ <b>Send new Support Text:</b>"
            markup = InlineKeyboardMarkup().add(ibtn("Cancel", callback_data="adm_sub_msgs", style="danger", custom_emoji_id=get_emoji_id("emj_cross")))
            if active_id:
                try: bot.edit_message_text(text, chat_id=chat_id, message_id=active_id, parse_mode="HTML", reply_markup=markup)
                except: pass
            bot.register_next_step_handler_by_chat_id(chat_id, process_edit_support)
        elif data_call == "edt_support_lnk":
            data = load_data()
            old_val = data.setdefault("texts", {}).get("support_link", "")
            active_id = admin_active_menus.get(str(chat_id))
            text = f"📌 <b>Current Support Link:</b>\n<code>{old_val}</code>\n\n🔗 <b>Send Support Account Link (starts with http):</b>"
            markup = InlineKeyboardMarkup().add(ibtn("Cancel", callback_data="adm_sub_msgs", style="danger", custom_emoji_id=get_emoji_id("emj_cross")))
            if active_id:
                try: bot.edit_message_text(text, chat_id=chat_id, message_id=active_id, parse_mode="HTML", reply_markup=markup)
                except: pass
            bot.register_next_step_handler_by_chat_id(chat_id, process_edit_support_link)
        elif data_call == "edt_otp_lnk":
            data = load_data()
            old_val = data.setdefault("texts", {}).get("otp_group_link", "")
            active_id = admin_active_menus.get(str(chat_id))
            text = f"📌 <b>Current OTP Link:</b>\n<code>{old_val}</code>\n\n🔗 <b>Send OTP Group Link:</b>"
            markup = InlineKeyboardMarkup().add(ibtn("Cancel", callback_data="adm_sub_msgs", style="danger", custom_emoji_id=get_emoji_id("emj_cross")))
            if active_id:
                try: bot.edit_message_text(text, chat_id=chat_id, message_id=active_id, parse_mode="HTML", reply_markup=markup)
                except: pass
            bot.register_next_step_handler_by_chat_id(chat_id, process_edit_otp_link)
        elif data_call == "edt_main_chan_lnk":
            data = load_data()
            old_val = data.setdefault("texts", {}).get("main_channel_link", "")
            active_id = admin_active_menus.get(str(chat_id))
            text = f"📌 <b>Current Main Channel Link:</b>\n<code>{old_val}</code>\n\n🔗 <b>Send New Main Channel Link (starts with http):</b>"
            markup = InlineKeyboardMarkup().add(ibtn("Cancel", callback_data="adm_sub_msgs", style="danger", custom_emoji_id=get_emoji_id("emj_cross")))
            if active_id:
                try: bot.edit_message_text(text, chat_id=chat_id, message_id=active_id, parse_mode="HTML", reply_markup=markup)
                except: pass
            bot.register_next_step_handler_by_chat_id(chat_id, process_edit_main_chan_link)
        elif data_call == "edt_renge_grp_lnk":
            data = load_data()
            old_val = data.setdefault("texts", {}).get("renge_group_link", "")
            active_id = admin_active_menus.get(str(chat_id))
            text = f"📌 <b>Current Renge Group Link:</b>\n<code>{old_val}</code>\n\n🔗 <b>Send New Renge Group Link (starts with http):</b>"
            markup = InlineKeyboardMarkup().add(ibtn("Cancel", callback_data="adm_sub_msgs", style="danger", custom_emoji_id=get_emoji_id("emj_cross")))
            if active_id:
                try: bot.edit_message_text(text, chat_id=chat_id, message_id=active_id, parse_mode="HTML", reply_markup=markup)
                except: pass
            bot.register_next_step_handler_by_chat_id(chat_id, process_edit_renge_grp_link)
        elif data_call == "edt_otp_bon":
            data = load_data()
            old_val = data.setdefault("settings", {}).get("otp_bonus", 0.001)
            active_id = admin_active_menus.get(str(chat_id))
            text = f"📌 <b>Current OTP Bonus:</b> <code>{old_val}$</code>\n\n💰 <b>Enter OTP Completion Reward ($):</b>"
            markup = InlineKeyboardMarkup().add(ibtn("Cancel", callback_data="adm_sub_rates", style="danger", custom_emoji_id=get_emoji_id("emj_cross")))
            if active_id:
                try: bot.edit_message_text(text, chat_id=chat_id, message_id=active_id, parse_mode="HTML", reply_markup=markup)
                except: pass
            bot.register_next_step_handler_by_chat_id(chat_id, process_edit_otp_bonus)
        elif data_call == "edt_ref_bon":
            data = load_data()
            old_val = data.setdefault("settings", {}).get("ref_bonus", 0.01)
            active_id = admin_active_menus.get(str(chat_id))
            text = f"📌 <b>Current Referral Bonus:</b> <code>{old_val}$</code>\n\n👥 <b>Enter Referral Reward Bonus ($):</b>"
            markup = InlineKeyboardMarkup().add(ibtn("Cancel", callback_data="adm_sub_rates", style="danger", custom_emoji_id=get_emoji_id("emj_cross")))
            if active_id:
                try: bot.edit_message_text(text, chat_id=chat_id, message_id=active_id, parse_mode="HTML", reply_markup=markup)
                except: pass
            bot.register_next_step_handler_by_chat_id(chat_id, process_edit_ref_bonus)
        elif data_call == "edt_min_wd":
            data = load_data()
            old_val = data.setdefault("settings", {}).get("min_withdraw", 0.3)
            active_id = admin_active_menus.get(str(chat_id))
            text = f"📌 <b>Current Minimum Withdraw:</b> <code>{old_val}$</code>\n\n📉 <b>Enter Minimum Withdrawal ($):</b>"
            markup = InlineKeyboardMarkup().add(ibtn("Cancel", callback_data="adm_sub_rates", style="danger", custom_emoji_id=get_emoji_id("emj_cross")))
            if active_id:
                try: bot.edit_message_text(text, chat_id=chat_id, message_id=active_id, parse_mode="HTML", reply_markup=markup)
                except: pass
            bot.register_next_step_handler_by_chat_id(chat_id, process_edit_min_withdraw)
        elif data_call == "edt_max_nums":
            data = load_data()
            old_val = data.setdefault("settings", {}).get("max_numbers", 3)
            active_id = admin_active_menus.get(str(chat_id))
            text = f"📌 <b>Current Maxrequested Numbers Limit:</b> <code>{old_val}</code>\n\n📱 <b>Enter Max requested numbers:</b>"
            markup = InlineKeyboardMarkup().add(ibtn("Cancel", callback_data="adm_sub_rates", style="danger", custom_emoji_id=get_emoji_id("emj_cross")))
            if active_id:
                try: bot.edit_message_text(text, chat_id=chat_id, message_id=active_id, parse_mode="HTML", reply_markup=markup)
                except: pass
            bot.register_next_step_handler_by_chat_id(chat_id, process_edit_max_numbers)

        elif data_call == "edt_btn_get_num":
            data = load_data()
            old_val = data.setdefault("texts", {}).get("btn_get_number", "GET NUMBER")
            active_id = admin_active_menus.get(str(chat_id))
            text = f"📌 <b>Current Button Text:</b> <code>{old_val}</code>\n\n✏️ <b>Enter custom text for Get Number Button:</b>"
            markup = InlineKeyboardMarkup().add(ibtn("Cancel", callback_data="adm_sub_btns", style="danger", custom_emoji_id=get_emoji_id("emj_cross")))
            if active_id:
                try: bot.edit_message_text(text, chat_id=chat_id, message_id=active_id, parse_mode="HTML", reply_markup=markup)
                except: pass
            bot.register_next_step_handler_by_chat_id(chat_id, process_edit_btn_get_num)
        elif data_call == "edt_btn_bal":
            data = load_data()
            old_val = data.setdefault("texts", {}).get("btn_balance", "BALANCE")
            active_id = admin_active_menus.get(str(chat_id))
            text = f"📌 <b>Current Button Text:</b> <code>{old_val}</code>\n\n✏️ <b>Enter custom text for Balance Button:</b>"
            markup = InlineKeyboardMarkup().add(ibtn("Cancel", callback_data="adm_sub_btns", style="danger", custom_emoji_id=get_emoji_id("emj_cross")))
            if active_id:
                try: bot.edit_message_text(text, chat_id=chat_id, message_id=active_id, parse_mode="HTML", reply_markup=markup)
                except: pass
            bot.register_next_step_handler_by_chat_id(chat_id, process_edit_btn_bal)
        elif data_call == "edt_btn_ref":
            data = load_data()
            old_val = data.setdefault("texts", {}).get("btn_refer", "REFER AND EARN")
            active_id = admin_active_menus.get(str(chat_id))
            text = f"📌 <b>Current Button Text:</b> <code>{old_val}</code>\n\n✏️ <b>Enter custom text for Refer & Earn Button:</b>"
            markup = InlineKeyboardMarkup().add(ibtn("Cancel", callback_data="adm_sub_btns", style="danger", custom_emoji_id=get_emoji_id("emj_cross")))
            if active_id:
                try: bot.edit_message_text(text, chat_id=chat_id, message_id=active_id, parse_mode="HTML", reply_markup=markup)
                except: pass
            bot.register_next_step_handler_by_chat_id(chat_id, process_edit_btn_ref)
        elif data_call == "edt_btn_sup":
            data = load_data()
            old_val = data.setdefault("texts", {}).get("btn_support", "SUPPORT")
            active_id = admin_active_menus.get(str(chat_id))
            text = f"📌 <b>Current Button Text:</b> <code>{old_val}</code>\n\n✏️ <b>Enter custom text for Support Button:</b>"
            markup = InlineKeyboardMarkup().add(ibtn("Cancel", callback_data="adm_sub_btns", style="danger", custom_emoji_id=get_emoji_id("emj_cross")))
            if active_id:
                try: bot.edit_message_text(text, chat_id=chat_id, message_id=active_id, parse_mode="HTML", reply_markup=markup)
                except: pass
            bot.register_next_step_handler_by_chat_id(chat_id, process_edit_btn_sup)
            
        elif data_call == "edt_lboard_days":
            data = load_data()
            old_val = data.setdefault("settings", {}).get("leaderboard_reset_days", 3)
            active_id = admin_active_menus.get(str(chat_id))
            text = f"📌 <b>Current Leaderboard Reset Days:</b> <code>{old_val} Days</code>\n\n📉 <b>Enter number of days for Leaderboard Auto Reset:</b>"
            markup = InlineKeyboardMarkup().add(ibtn("Cancel", callback_data="adm_sub_rates", style="danger", custom_emoji_id=get_emoji_id("emj_cross")))
            if active_id:
                try: bot.edit_message_text(text, chat_id=chat_id, message_id=active_id, parse_mode="HTML", reply_markup=markup)
                except: pass
            bot.register_next_step_handler_by_chat_id(chat_id, process_edit_lboard_days)

        elif data_call == "admin_extras":
            show_admin_extras(chat_id, msg_id)
            
        elif data_call == "toggle_m_mode":
            data = load_data()
            curr = data.get("maintenance_mode", False)
            data["maintenance_mode"] = not curr
            save_data(data)
            bot.answer_callback_query(call.id, f"Maintenance Mode turned {'ON' if not curr else 'OFF'}!", show_alert=True)
            show_admin_extras(chat_id, msg_id)
            
        elif data_call == "toggle_admin_alerts":
            data = load_data()
            curr = data.get("settings", {}).get("admin_alerts", True)
            data.setdefault("settings", {})["admin_alerts"] = not curr
            save_data(data)
            bot.answer_callback_query(call.id, f"Admin Alerts turned {'ON' if not curr else 'OFF'}!", show_alert=True)
            show_admin_extras(chat_id, msg_id)
            
        elif data_call == "toggle_alert_type":
            data = load_data()
            curr = data.get("settings", {}).get("only_member_join_alert", True)
            data.setdefault("settings", {})["only_member_join_alert"] = not curr
            save_data(data)
            bot.answer_callback_query(call.id, f"Alert Type changed to {'Only Member Join' if not curr else 'All Alerts'}!", show_alert=True)
            show_admin_extras(chat_id, msg_id)
            
        elif data_call == "set_m_msg":
            active_id = admin_active_menus.get(str(chat_id))
            text = "✏️ <b>Enter new Maintenance Message (HTML supported):</b>"
            markup = InlineKeyboardMarkup().add(ibtn("Cancel", callback_data="admin_extras", style="danger", custom_emoji_id=get_emoji_id("emj_cross")))
            if active_id:
                try: bot.edit_message_text(text, chat_id=chat_id, message_id=active_id, parse_mode="HTML", reply_markup=markup)
                except: pass
            bot.register_next_step_handler_by_chat_id(chat_id, process_set_m_msg)
            
        elif data_call == "sys_stats":
            import sys
            import platform
            db_size = os.path.getsize(DATA_FILE) / 1024 if os.path.exists(DATA_FILE) else 0
            stats_text = (
                f"<b>📊 SYSTEM STATISTICS</b>\n\n"
                f"▫️ <b>OS Platform:</b> <code>{platform.system()} {platform.release()}</code>\n"
                f"▫️ <b>Python Version:</b> <code>{sys.version.split()[0]}</code>\n"
                f"▫️ <b>Database Size:</b> <code>{db_size:.2f} KB</code>\n"
                f"▫️ <b>Total Registered Users:</b> <code>{len(load_data().get('users', []))}</code>"
            )
            markup = InlineKeyboardMarkup().add(ibtn("BACK", callback_data="admin_extras", style="primary", custom_emoji_id=get_emoji_id("emj_cross")))
            try: bot.edit_message_text(stats_text, chat_id=chat_id, message_id=msg_id, parse_mode="HTML", reply_markup=markup)
            except: pass
            
        elif data_call == "manual_lboard_reset":
            data = load_data()
            data["leaderboard"] = {"last_reset": time.time(), "stats": {}}
            save_data(data)
            bot.answer_callback_query(call.id, "Leaderboard manually reset successfully!", show_alert=True)
            show_admin_extras(chat_id, msg_id)
            
        elif data_call == "db_backup":
            if os.path.exists(DATA_FILE):
                with open(DATA_FILE, "rb") as f:
                    bot.send_document(chat_id, f, caption="<b>Database Backup (JSON)</b>", parse_mode="HTML")
            else:
                bot.answer_callback_query(call.id, "Database file not found!", show_alert=True)
                
        elif data_call == "otp_broadcast":
            data = load_data()
            groups = data.get("forward_groups", [])
            if not groups:
                bot.answer_callback_query(call.id, "No forward groups configured!", show_alert=True)
                return
            active_id = admin_active_menus.get(str(chat_id))
            text = "📢 <b>Enter OTP Broadcast Message to send to all forward groups:</b>"
            markup = InlineKeyboardMarkup().add(ibtn("Cancel", callback_data="admin_extras", style="danger", custom_emoji_id=get_emoji_id("emj_cross")))
            if active_id:
                try: bot.edit_message_text(text, chat_id=chat_id, message_id=active_id, parse_mode="HTML", reply_markup=markup)
                except: pass
            bot.register_next_step_handler_by_chat_id(chat_id, process_otp_broadcast)
            
        elif data_call == "list_banned":
            data = load_data()
            banned = data.get("banned_users", [])
            if banned:
                b_text = "<b>🚫 BANNED USERS LIST</b>\n\n" + "\n".join([f"- <code>{u}</code>" for u in banned])
            else:
                b_text = "<b>🚫 BANNED USERS LIST</b>\n\n<i>No banned users found.</i>"
            markup = InlineKeyboardMarkup().add(ibtn("BACK", callback_data="admin_extras", style="primary", custom_emoji_id=get_emoji_id("emj_cross")))
            try: bot.edit_message_text(b_text, chat_id=chat_id, message_id=msg_id, parse_mode="HTML", reply_markup=markup)
            except: pass
            
        elif data_call == "list_withdrawals":
            data = load_data()
            pending = data.get("pending_withdrawals", {})
            if pending:
                w_text = "<b>💸 PENDING WITHDRAWALS</b>\n\n"
                for req_id, req in pending.items():
                    w_text += f"▫️ ID: <code>{req['uid']}</code> | {req['amount']}$ ({req['method']}) -> <code>{req['address']}</code>\n"
            else:
                w_text = "<b>💸 PENDING WITHDRAWALS</b>\n\n<i>No pending requests found.</i>"
            markup = InlineKeyboardMarkup().add(ibtn("BACK", callback_data="admin_extras", style="primary", custom_emoji_id=get_emoji_id("emj_cross")))
            try: bot.edit_message_text(w_text, chat_id=chat_id, message_id=msg_id, parse_mode="HTML", reply_markup=markup)
            except: pass
            
        elif data_call == "clear_temp":
            cleared = 0
            for file in os.listdir("."):
                if file.endswith(".txt") and file.startswith("all_users"):
                    try:
                        os.remove(file)
                        cleared += 1
                    except: pass
            bot.answer_callback_query(call.id, f"Cleared {cleared} temp files!", show_alert=True)
            show_admin_extras(chat_id, msg_id)
            
        elif data_call == "active_sessions_count":
            count = len(active_sessions)
            bot.answer_callback_query(call.id, f"Currently {count} active OTP polling sessions.", show_alert=True)
            show_admin_extras(chat_id, msg_id)

        # --- EXECUTOR SYSTEM CALLS FOR NEW ADMIN FEATURES ---
        elif data_call == "adm_check_api_bal":
            check_api_provider_balance(chat_id, msg_id)
        elif data_call == "adm_export_csv":
            export_users_csv(chat_id)
            bot.answer_callback_query(call.id, "CSV Database exported successfully!", show_alert=True)
            show_admin_extras(chat_id, msg_id)
        elif data_call == "adm_db_optimize":
            optimize_database_system(chat_id, msg_id)
            bot.answer_callback_query(call.id, "System Database Optimized!", show_alert=True)

        elif data_call == "admin_groups":
            show_admin_forward_groups(chat_id, msg_id)
        elif data_call == "add_fwd_grp":
            active_id = admin_active_menus.get(str(chat_id))
            text = "💬 <b>Send Target Group ID(s):</b>\n<i>(You can send a single ID like <code>-100xxxxx</code>, or multiple IDs separated by commas, spaces, or newlines)</i>"
            markup = InlineKeyboardMarkup().add(ibtn("Cancel", callback_data="admin_groups", style="danger", custom_emoji_id=get_emoji_id("emj_cross")))
            if active_id:
                try: bot.edit_message_text(text, chat_id=chat_id, message_id=active_id, parse_mode="HTML", reply_markup=markup)
                except: pass
            bot.register_next_step_handler_by_chat_id(chat_id, process_add_group)
        elif data_call.startswith("del_fwd_grp|"):
            idx = int(data_call.split("|")[1])
            data = load_data()
            groups = data.setdefault("forward_groups", [])
            if 0 <= idx < len(groups):
                removed = groups.pop(idx)
                save_data(data)
                bot.answer_callback_query(call.id, f"Removed group {removed}", show_alert=True)
            show_admin_forward_groups(chat_id, msg_id)

        elif data_call == "admin_search_user":
            active_id = admin_active_menus.get(str(chat_id))
            text = "🔍 <b>Send User ID to check data:</b>"
            markup = InlineKeyboardMarkup().add(ibtn("Cancel", callback_data="back_to_admin", style="danger", custom_emoji_id=get_emoji_id("emj_cross")))
            if active_id:
                try: bot.edit_message_text(text, chat_id=chat_id, message_id=active_id, parse_mode="HTML", reply_markup=markup)
                except: pass
            bot.register_next_step_handler_by_chat_id(chat_id, process_search_user)
        elif data_call == "admin_users_count":
            data = load_data()
            users = data.get("users", [])
            
            if not users:
                bot.send_message(chat_id, "No users registered yet!", parse_mode="HTML")
                return
                
            file_path = "all_users.txt"
            with open(file_path, "w") as f:
                for u in users:
                    f.write(f"{u}\n")
                    
            with open(file_path, "rb") as f:
                bot.send_document(chat_id, f, caption=f"<b>Total users logged in from opening:</b> <code>{len(users)}</code>", parse_mode="HTML")
                
            try: os.remove(file_path)
            except: pass
            
        elif data_call == "admin_manage_admins":
            show_admin_manage_admins_view(chat_id, msg_id)
            
        elif data_call == "add_admin_id":
            active_id = admin_active_menus.get(str(chat_id))
            text = f"<b>Send the User ID you want to grant Admin access to:</b>"
            markup = InlineKeyboardMarkup().add(ibtn("Cancel", callback_data="admin_manage_admins", style="danger", custom_emoji_id=get_emoji_id("emj_cross")))
            if active_id:
                try: bot.edit_message_text(text, chat_id=chat_id, message_id=active_id, parse_mode="HTML", reply_markup=markup)
                except: pass
            bot.register_next_step_handler_by_chat_id(chat_id, process_add_admin)
            
        elif data_call == "remove_admin_id":
            active_id = admin_active_menus.get(str(chat_id))
            text = f"<b>Send the Admin ID you want to remove access from:</b>"
            markup = InlineKeyboardMarkup().add(ibtn("Cancel", callback_data="admin_manage_admins", style="danger", custom_emoji_id=get_emoji_id("emj_cross")))
            if active_id:
                try: bot.edit_message_text(text, chat_id=chat_id, message_id=active_id, parse_mode="HTML", reply_markup=markup)
                except: pass
            bot.register_next_step_handler_by_chat_id(chat_id, process_remove_admin)
            
        elif data_call == "admin_balance":
            active_id = admin_active_menus.get(str(chat_id))
            text = "💰 <b>Send User ID to manage balance:</b>"
            markup = InlineKeyboardMarkup().add(ibtn("Cancel", callback_data="back_to_admin", style="danger", custom_emoji_id=get_emoji_id("emj_cross")))
            if active_id:
                try: bot.edit_message_text(text, chat_id=chat_id, message_id=active_id, parse_mode="HTML", reply_markup=markup)
                except: pass
            bot.register_next_step_handler_by_chat_id(chat_id, process_admin_balance_search)
            
        elif data_call.startswith("adm_bal_add|"):
            uid = data_call.split("|")[1]
            active_id = admin_active_menus.get(str(chat_id))
            text = f"<b>Enter amount to ADD for {uid}:</b>"
            markup = InlineKeyboardMarkup().add(ibtn("Cancel", callback_data="back_to_admin", style="danger", custom_emoji_id=get_emoji_id("emj_cross")))
            if active_id:
                try: bot.edit_message_text(text, chat_id=chat_id, message_id=active_id, parse_mode="HTML", reply_markup=markup)
                except: pass
            bot.register_next_step_handler_by_chat_id(chat_id, process_add_bal, uid)
            
        elif data_call.startswith("adm_bal_cut|"):
            uid = data_call.split("|")[1]
            active_id = admin_active_menus.get(str(chat_id))
            text = f"<b>Enter amount to DEDUCT for {uid}:</b>"
            markup = InlineKeyboardMarkup().add(ibtn("Cancel", callback_data="back_to_admin", style="danger", custom_emoji_id=get_emoji_id("emj_cross")))
            if active_id:
                try: bot.edit_message_text(text, chat_id=chat_id, message_id=active_id, parse_mode="HTML", reply_markup=markup)
                except: pass
            bot.register_next_step_handler_by_chat_id(chat_id, process_cut_bal, uid)
    except Exception as e:
        try: bot.send_message(ADMIN_ID, f"Error in Callback handler: {str(e)}")
        except: pass

# ============================================
# --- RUN THE BOT SAFELY ---
# ============================================
if __name__ == "__main__":
    # --- Start Flask Server in Background ---
    server_thread = threading.Thread(target=run_server)
    server_thread.daemon = True
    server_thread.start()

    try:
        print("Clearing previous webhook conflicts...")
        bot.remove_webhook()
    except Exception as e:
        print(f"Webhook clean status: {e}")
        
    print("RM XEL Bot is running successfully...")
    bot.infinity_polling()


