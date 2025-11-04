# bot.py
import os
import re
import time
import logging
import requests
import feedparser
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator, MyMemoryTranslator
import schedule
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import html
from db_supabase import is_seen, mark_seen

# ================== НАСТРОЙКИ ==================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@time_n_John")
DATABASE_URL = os.getenv("DATABASE_URL")

if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN не задан")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL (Supabase) не задан")

# RSS-источники (работают через feedparser)
RSS_SOURCES = [
    {"name": "E3G", "url": "https://www.e3g.org/feed/"},
    {"name": "Foreign Affairs", "url": "https://www.foreignaffairs.com/rss.xml"},
    {"name": "Reuters Institute", "url": "https://reutersinstitute.politics.ox.ac.uk/rss.xml"},
    {"name": "Bruegel", "url": "https://www.bruegel.org/rss.xml"},
    {"name": "Chatham House", "url": "https://www.chathamhouse.org/rss.xml"},
    {"name": "CSIS", "url": "https://www.csis.org/rss.xml"},
    {"name": "Atlantic Council", "url": "https://www.atlanticcouncil.org/feed/"},
    {"name": "RAND Corporation", "url": "https://www.rand.org/rss.xml"},
    {"name": "CFR", "url": "https://www.cfr.org/rss/"},
    {"name": "The Economist", "url": "https://www.economist.com/latest/rss.xml"},
    {"name": "Bloomberg Politics", "url": "https://www.bloomberg.com/politics/feeds/site.xml"},
]

# HTML-источники (работают через BeautifulSoup)
HTML_SOURCES = [
    {"n": "Good Judgment", "u": "https://goodjudgment.com/open-questions/", "s": ".question-title a", "b": "https://goodjudgment.com"},
    {"n": "Johns Hopkins", "u": "https://centerforhealthsecurity.org/news/", "s": "h3.post-title a", "b": "https://centerforhealthsecurity.org"},
    {"n": "Metaculus", "u": "https://www.metaculus.com/questions/", "s": ".question-name a", "b": "https://www.metaculus.com"},
    {"n": "DNI", "u": "https://www.dni.gov/index.php/gt2040-home", "s": "h3 a, h2 a", "b": "https://www.dni.gov"},
    {"n": "RAND", "u": "https://www.rand.org/pubs.html", "s": "h3.pub-title a", "b": "https://www.rand.org"},
    {"n": "WEF", "u": "https://www.weforum.org/agenda/", "s": "h3[data-module='article-title'] a", "b": "https://www.weforum.org"},
    {"n": "CSIS", "u": "https://www.csis.org/analysis", "s": "h3.field--name-title a", "b": "https://www.csis.org"},
    {"n": "Atlantic", "u": "https://www.atlanticcouncil.org/blogs/", "s": "h3.post-title a", "b": "https://www.atlanticcouncil.org"},
    {"n": "Chatham", "u": "https://www.chathamhouse.org/publications", "s": "h3.publication-title a", "b": "https://www.chathamhouse.org"},
    {"n": "Economist", "u": "https://www.economist.com", "s": "h3.teaser__headline a", "b": "https://www.economist.com"},
    {"n": "Bloomberg", "u": "https://www.bloomberg.com", "s": "h3.storyItem__headline a", "b": "https://www.bloomberg.com"},
    {"n": "Reuters Inst", "u": "https://reutersinstitute.politics.ox.ac.uk/news", "s": "h3.news-title a", "b": "https://reutersinstitute.politics.ox.ac.uk"},
    {"n": "Foreign Affairs", "u": "https://www.foreignaffairs.com/articles", "s": "h3.view-content-title a", "b": "https://www.foreignaffairs.com"},
    {"n": "CFR", "u": "https://www.cfr.org/news", "s": "h3.node__title a", "b": "https://www.cfr.org"},
    {"n": "BBC Future", "u": "https://www.bbc.com/future", "s": "h2[data-testid='card-headline'] a", "b": "https://www.bbc.com"},
    {"n": "Future Timeline", "u": "https://futuretimeline.net", "s": "h3.entry-title a", "b": "https://futuretimeline.net"},
    {"n": "Carnegie", "u": "https://carnegieendowment.org/publications", "s": "h3.pub-title a", "b": "https://carnegieendowment.org"},
    {"n": "Bruegel", "u": "https://www.bruegel.org/publications", "s": "h3.publication-title a", "b": "https://www.bruegel.org"},
    {"n": "E3G", "u": "https://www.e3g.org/news/", "s": "h3.post-title a", "b": "https://www.e3g.org"},
]

# 🔥 Расширенные ключевые слова (включая всё, что вы просили)
KEYWORDS = [
   r"\brussia\b", r"\brussian\b", r"\bputin\b", r"\bmoscow\b", r"\bkremlin\b",
   r"\bukraine\b", r"\bukrainian\b", r"\bzelensky\b", r"\bkyiv\b", r"\bkiev\b",
   r"\bcrimea\b", r"\bdonbas\b", r"\bsanction[s]?\b", r"\bgazprom\b",
   r"\bnord\s?stream\b", r"\bwagner\b", r"\blavrov\b", r"\bshoigu\b",
   r"\bmedvedev\b", r"\bpeskov\b", r"\bnato\b", r"\beuropa\b", r"\busa\b",
   r"\bsoviet\b", r"\bussr\b", r"\bpost\W?soviet\b",
   # === СВО и Война ===
   r"\bsvo\b", r"\bспецоперация\b", r"\bspecial military operation\b",
   r"\bвойна\b", r"\bwar\b", r"\bconflict\b", r"\bконфликт\b",
   r"\bнаступление\b", r"\boffensive\b", r"\bатака\b", r"\battack\b",
   r"\bудар\b", r"\bstrike\b", r"\bобстрел\b", r"\bshelling\b",
   r"\bдрон\b", r"\bdrone\b", r"\bmissile\b", r"\bракета\b",
   r"\bэскалация\b", r"\bescalation\b", r"\bмобилизация\b", r"\bmobilization\b",
   r"\bфронт\b", r"\bfrontline\b", r"\bзахват\b", r"\bcapture\b",
   r"\bосвобождение\b", r"\bliberation\b", r"\bбой\b", r"\bbattle\b",
   r"\bпотери\b", r"\bcasualties\b", r"\bпогиб\b", r"\bkilled\b",
   r"\bранен\b", r"\binjured\b", r"\bпленный\b", r"\bprisoner of war\b",
   r"\bпереговоры\b", r"\btalks\b", r"\bперемирие\b", r"\bceasefire\b",
   r"\bсанкции\b", r"\bsanctions\b", r"\bоружие\b", r"\bweapons\b",
   r"\bпоставки\b", r"\bsupplies\b", r"\bhimars\b", r"\batacms\b",
   r"\bhour ago\b", r"\bчас назад\b", r"\bminutos atrás\b", r"\b小时前\b",
   # === Криптовалюта (топ-20 + CBDC, DeFi, регуляция) ===
   r"\bbitcoin\b", r"\bbtc\b", r"\bбиткоин\b", r"\b比特币\b",
   r"\bethereum\b", r"\beth\b", r"\bэфир\b", r"\b以太坊\b",
   r"\bbinance coin\b", r"\bbnb\b", r"\busdt\b", r"\btether\b",
   r"\bxrp\b", r"\bripple\b", r"\bcardano\b", r"\bada\b",
   r"\bsolana\b", r"\bsol\b", r"\bdoge\b", r"\bdogecoin\b",
   r"\bavalanche\b", r"\bavax\b", r"\bpolkadot\b", r"\bdot\b",
   r"\bchainlink\b", r"\blink\b", r"\btron\b", r"\btrx\b",
   r"\bcbdc\b", r"\bcentral bank digital currency\b", r"\bцифровой рубль\b",
   r"\bdigital yuan\b", r"\beuro digital\b", r"\bdefi\b", r"\bдецентрализованные финансы\b",
   r"\bnft\b", r"\bnon-fungible token\b", r"\bsec\b", r"\bцб рф\b",
   r"\bрегуляция\b", r"\bregulation\b", r"\bзапрет\b", r"\bban\b",
   r"\bмайнинг\b", r"\bmining\b", r"\bhalving\b", r"\bхалвинг\b",
   r"\bволатильность\b", r"\bvolatility\b", r"\bcrash\b", r"\bкрах\b",
   r"\b刚刚\b", r"\bدقائق مضت\b",
   # === Пандемия и болезни (включая биобезопасность) ===
   r"\bpandemic\b", r"\bпандемия\b", r"\b疫情\b", r"\bجائحة\b",
   r"\boutbreak\b", r"\bвспышка\b", r"\bэпидемия\b", r"\bepidemic\b",
   r"\bvirus\b", r"\bвирус\b", r"\bвирусы\b", r"\b变异株\b",
   r"\bvaccine\b", r"\bвакцина\b", r"\b疫苗\b", r"\bلقاح\b",
   r"\bbooster\b", r"\bбустер\b", r"\bревакцинация\b",
   r"\bquarantine\b", r"\bкарантин\b", r"\b隔离\b", r"\bحجر صحي\b",
   r"\blockdown\b", r"\bлокдаун\b", r"\b封锁\b",
   r"\bmutation\b", r"\bмутация\b", r"\b变异\b",
   r"\bstrain\b", r"\bштамм\b", r"\bomicron\b", r"\bdelta\b",
   r"\bbiosafety\b", r"\bбиобезопасность\b", r"\b生物安全\b",
   r"\blab leak\b", r"\bлабораторная утечка\b", r"\b实验室泄漏\b",
   r"\bgain of function\b", r"\bусиление функции\b",
   r"\bwho\b", r"\bвоз\b", r"\bcdc\b", r"\bроспотребнадзор\b",
   r"\binfection rate\b", r"\bзаразность\b", r"\b死亡率\b",
   r"\bhospitalization\b", r"\bгоспитализация\b",
   r"\bقبل ساعات\b", r"\b刚刚报告\b"
]

MAX_PER_RUN = 15
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

def clean_text(t):
    return re.sub(r"\s+", " ", t).strip() if t else ""

def translate_to_russian(text):
    if not text.strip():
        return text
    try:
        return GoogleTranslator(source='auto', target='ru').translate(text[:2000])
    except Exception as e1:
        log.warning(f"Google Translate failed: {e1}")
        try:
            return MyMemoryTranslator(source='en', target='ru').translate(text[:2000])
        except Exception as e2:
            log.warning(f"MyMemoryTranslator failed: {e2}")
            return text

def get_source_prefix(name):
    mapping = {
        "e3g": "e3g",
        "foreign affairs": "foreignaffairs",
        "chatham house": "chathamhouse",
        "csis": "csis",
        "atlantic council": "atlanticcouncil",
        "rand": "rand",
        "cfr": "cfr",
        "bruegel": "bruegel",
        "bloomberg": "bloomberg",
        "reuters institute": "reuters",
        "the economist": "economist"
    }
    name_lower = name.lower()
    for key in mapping:
        if key in name_lower:
            return mapping[key]
    return name.split()[0].lower()

def fetch_news():
    result = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    # === 1. Обработка RSS-источников ===
    for src in RSS_SOURCES:
        if len(result) >= MAX_PER_RUN:
            break
        try:
            url = src["url"].strip()
            log.info(f"📡 RSS {src['name']}: {url}")
            feed = feedparser.parse(url)
            for entry in feed.entries[:10]:
                if len(result) >= MAX_PER_RUN:
                    break
                title = clean_text(entry.get("title", ""))
                link = clean_text(entry.get("link", ""))
                if not title or not link or is_seen(link, title):
                    continue
                if not any(re.search(kw, title, re.IGNORECASE) for kw in KEYWORDS):
                    continue
                
                desc = clean_text(entry.get("summary", ""))
                content = clean_text(
                    entry.get("content", [{}])[0].get("value", "") if entry.get("content") else ""
                )
                lead = (desc or content or "").strip()
                if not lead:
                    lead = title
                
                sentences = re.split(r'(?<=[.!?])\s+', lead)
                if len(sentences) > 2:
                    lead = ' '.join(sentences[:2]).rstrip() + "…"
                else:
                    lead = lead.rstrip()
                
                ru_title = translate_to_russian(title)
                ru_lead = translate_to_russian(lead)
                prefix = get_source_prefix(src["name"]).upper()
                safe_prefix = html.escape(prefix)
                safe_title = html.escape(ru_title)
                safe_lead = html.escape(ru_lead)
                safe_link = html.escape(link)
                
                msg = f"<b>{safe_prefix}</b>: {safe_title}\n\n{safe_lead}\n\nИсточник: {safe_link}"
                result.append({"msg": msg, "link": link, "title": title})
        except Exception as e:
            log.error(f"❌ RSS {src['name']}: {e}")

    # === 2. Обработка HTML-источников ===
    for src in HTML_SOURCES:
        if len(result) >= MAX_PER_RUN:
            break
        try:
            base_url = src["b"].rstrip("/")
            page_url = src["u"].strip()
            selector = src["s"]
            log.info(f"🌐 HTML {src['n']}: {page_url}")
            resp = requests.get(page_url, headers=headers, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.content, "html.parser")
            items = soup.select(selector)
            for item in items[:10]:
                if len(result) >= MAX_PER_RUN:
                    break
                a_tag = item if item.name == 'a' else item.find('a')
                if not a_tag or not a_tag.get_text(strip=True) or not a_tag.get('href'):
                    continue
                
                link = a_tag['href'].strip()
                title = clean_text(a_tag.get_text())
                
                if link.startswith('/'):
                    link = base_url + link
                elif not link.startswith('http'):
                    continue
                
                if not title or is_seen(link, title):
                    continue
                
                if not any(re.search(kw, title, re.IGNORECASE) for kw in KEYWORDS):
                    continue
                
                ru_title = translate_to_russian(title)
                ru_lead = ru_title  # Для HTML-источников используем заголовок как лид
                
                safe_prefix = html.escape(src["n"])
                safe_title = html.escape(ru_title)
                safe_lead = html.escape(ru_lead)
                safe_link = html.escape(link)
                
                msg = f"<b>{safe_prefix}</b>: {safe_title}\n\n{safe_lead}\n\nИсточник: {safe_link}"
                result.append({"msg": msg, "link": link, "title": title})
        except Exception as e:
            log.error(f"❌ HTML {src['n']}: {e}")

    return result

def send_to_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHANNEL_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
        r = requests.post(url, data=payload, timeout=15)
        if r.status_code == 200:
            log.info("✅ Отправлено")
        else:
            log.error(f"❌ Telegram error: {r.status_code} {r.text}")
    except Exception as e:
        log.error(f"❌ Исключение при отправке: {e}")

def job_main():
    try:
        log.info("🔄 Основная проверка новостей...")
        news = fetch_news()
        if not news:
            log.info("📭 Нет релевантных новостей.")
            return
        for item in news:
            send_to_telegram(item["msg"])
            mark_seen(item["link"], item["title"])
            time.sleep(2)
    except Exception as e:
        log.exception("🚨 Критическая ошибка в job_main")

def job_keepalive():
    log.info("💤 Keep-alive check")

# ================== HTTP сервер для Render ==================
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
    def log_message(self, format, *args):
        pass

def start_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    server.serve_forever()

# ================== MAIN ==================
if __name__ == "__main__":
    threading.Thread(target=start_server, daemon=True).start()
    log.info("🚀 Бот запущен. Проверка каждые 14 минут.")

    job_main()
    schedule.every(14).minutes.do(job_main)
    schedule.every(10).minutes.do(job_keepalive)

    while True:
        schedule.run_pending()
        time.sleep(1)
