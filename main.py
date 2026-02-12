
# file: bot1_openA.py
from telethon import TelegramClient, events, Button
from telethon.tl.types import User
from datetime import datetime, timedelta
from functools import lru_cache
import re, os, traceback, tempfile

# ✅ API ma'lumotlari (o'zingizniki)
api_id = 20439154
api_hash = "3125ce8355eebd911e56d564d643bb64"
client = TelegramClient("bot1_openA", api_id, api_hash)

# 🛡 Railway uchun instance nazorati
lock_path = os.path.join(tempfile.gettempdir(), "bot.lock")
if os.environ.get("RAILWAY_INSTANCE") and os.path.exists(lock_path):
    print("❌ Oldingi instance ishlayapti, chiqyapti...")
    raise SystemExit(0)
else:
    open(lock_path, "w").close()

SOURCE_CHAT_IDS = []


GROUP_LINKS = {}


# ===== Normalizatsiya (emoji + translit + typo tuzatish) =====
try:
    import emoji
    EMOJI_AVAILABLE = True
except Exception:
    EMOJI_AVAILABLE = False

def normalize_text(text: str) -> str:
    if not text:
        return ""
    if EMOJI_AVAILABLE:
        text = emoji.replace_emoji(text, replace="")
    text = text.lower()
    text = re.sub(r'["“”’‘´]', '', text)
    text = re.sub(r'[.,!?\-]', '', text)
    text = re.sub(r'\bbo\b', 'bor', text)
    text = re.sub(r'\s+', ' ', text)

    # Kirill → Lotin
    rep = {
        "а":"a","б":"b","в":"v","г":"g","д":"d","е":"e","ё":"yo","ж":"j","з":"z","и":"i","й":"y","к":"k",
        "л":"l","м":"m","н":"n","о":"o","п":"p","р":"r","с":"s","т":"t","у":"u","ф":"f","х":"x","ц":"ts",
        "ч":"ch","ш":"sh","щ":"sh","ъ":"","ы":"i","ь":"","э":"e","ю":"yu","я":"ya","қ":"q","ў":"o‘",
        "ғ":"g‘","ҳ":"h"
    }
    for k, v in rep.items():
        text = text.replace(k, v)

    misspellings = {
        "olamz":"olamiz","olmz":"olamiz","olip":"olib","olam":"olaman",
        "olibketaman":"olib ketaman","olibketamz":"olib ketamiz","ketamz":"ketamiz",
        "poxta":"pochta","pachta":"pochta","pocht":"pochta","pochchala":"pochta",
        "pochchta":"pochta","pochchani":"pochta","pocholamiz":"pochta olamiz",
        "jentira":"jentra","jntra":"jentra","gentra":"jentra",
        "kapteva":"kaptiva","captva":"captiva","captivaa":"captiva",
        "kobolt":"kobalt","koblat":"kobalt","koblt":"kobalt",
        "machina":"mashina","mosina":"moshina","moshinaa":"moshina",
        "komport":"komfort","komporti":"komfort","komford":"komfort",
        "lichkda":"lichkada","lichkaga yoz":"lichkada yozing","olmiz":"olamiz",
        "odam migrim":"migirim","pochta migrim":"migirim","odam tolgan":"odam tolgan"
    }
    for wrong, correct in misspellings.items():
        text = text.replace(wrong, correct)

    text = re.sub(r'\s+', ' ', text).strip()
    return text

# 🎤 Ovozni aniqlash
def is_voice_message(event) -> bool:
    if getattr(event.message, "voice", None):
        return True
    if event.message.media and hasattr(event.message.media, 'document'):
        mime = event.message.media.document.mime_type
        return bool(mime and mime.startswith("audio/"))
    return False

# 📍 Yo'nalish aniqlash (oddiy)
def extract_direction(text: str) -> str:
    t = (text or "").lower()
    directions = [
        ("toshkent", "namangan", "Toshkent➡️ Namangan", "Namangan ➡️ Toshkent"),
        ("toshkent", "andijon", "Toshkent ➡️ Andijon", "Andijon ➡️ Toshkent"),
        ("toshkent", "fargona", "Toshkent ➡️ Farg‘ona", "Farg‘ona ➡️ Toshkent"),
        ("toshkent", "angren", "Toshkent ➡️ Angren", "Angren ➡️ Toshkent"),
        ("toshkent", "qoqon",  "Toshkent ➡️ Qo‘qon",  "Qo‘qon ➡️ Toshkent"),
    ]
    for c1, c2, d1, d2 in directions:
        if c1 in t and c2 in t:
            return d1 if t.find(c1) < t.find(c2) else d2
    return "Yo‘nalish aniqlanmadi"

# ✅ 1-daraja: reklama bloklash
def level_1_check(text):
    blacklist = [
        "1xbet","stavka","reklama","admin","konditsioner","kondi","bepul",
        "kanalga azo","obuna","lotereya","telegram","bot","stream","youtube",
        "instagram","tiktok","like bosing","ish bor","lichkaga yoz","biznes",
        "sotiladi","kredit","kurs","konkurs","promo","chegirma","to‘lov asosida","rasmiy"
    ]
    patterns = [
        r'http[s]?://', r'www\.', r'@\w{3,}', r'\.uz\b|\.com\b|\.ru\b|\.org\b',
        r'\w+@\w+\.\w+', r'\bbot\b', r'\bjoin\b', r'\bchannel\b'
    ]
    if any(w in text for w in blacklist):
        return False
    if any(re.search(p, text) for p in patterns):
        return False
    return True

# ❌ 2-daraja: haydovchi gaplarini bloklash
def level_2_check(text):
    driver_phrases_main = [
        "olib ketaman","joy bor","sherik kerak","bo‘sh joy","yo‘lman","yuryapmiz","yuramiz",
        "1ta kam","2ta kam","3ta kam","1 kam","2 kam","1kam","kamdamiz","kam","oldi bosh",
        "jentra","kimga kerak","pochta kerak","pochta olaman","pochta olamiz",
        "yuk olib ketaman","olib chiqaman","komu nado","moshina kaptiva","lasetti","avto",
        "konditsioner","kondi","kandissaner","kanditsaner","ayol kishi bor","haydovchi","cobalt",
        "pochta olib ketaman","pochta olaman","pochta olamiz","pochta olish",
        "1 kishi kerak","2 kishi kerak","3 kishi kerak","4 kishi kerak",
        "1 odam migrim","2 odam migrim","3 odam migrim","migirim","pochta migirim","odam migrim",
        "pochtala","pochchala","pochtani olaman","xarktdamz olaman","olamiz","bulsa olamiz",
        "yurimiz","olib ketamiz","olib ketamz"
    ]
    driver_phrases_extended = [
        "odam olamiz","po'shta olamiz","poshta olamiz","oldi mesta","oldi joy","oldi joy bor",
        "oldi mestaga","mashina bor","moshina bor","mashina komfort","komfort","kobolt","kobalt",
        "mashina kobalt","mashina kaptiva","captiva","mashina chiqdi","moshina ketdi","mashina ketayapti",
        "lichkada","lichkada yozing","lichkada bor","tel lichada","bosh joy","joy ochiq","joy qoldi",
        "faqat ayollar","ayollar bor","ayol bor","ayol kishi","mashina bekor","mashina pustoy",
        "mashina bo‘sh","pustoy","moshina bo‘sh","moshina pustoy","olip ketamiz","odam pochta olmz",
        "odam olmz","pochta olmz","xarakatdamiz","yuramiz","olaman","yuraman","bosa olamz","bosa ketamz","bosa yuramz"
    ]
    if any(p in text for p in (driver_phrases_main + driver_phrases_extended)):
        return False
    return True

# 📏 3-daraja: uzunlik
def level_3_check(text):
    return 5 <= len(text) <= 150 and len(text.split()) >= 2

# ❌ 5-daraja: ziddiyat
def level_5_check(text):
    return not ("bor" in text and ("ketamiz" in text or "chiqamiz" in text))

# ⚠️ 6-daraja: shoshilinch
@lru_cache(maxsize=512)
def level_6_check(text):
    urgent = [
        "tezda","tezroq","darrov","srochna","sroshna","sroshniga","srochno","srochnoy","srchna",
        "zudlik bilan","zudlikbln","zudlikbn","hoziroq","shu zahoti","vaqtida yetishishim kerak",
        "bu vaqtda kerak","darxol","zamonida","hozi chiqaman","tez olib ketish","tez olib borish",
        "tez yetkaz","tez yetkizish"
    ]
    return any(k in text for k in urgent)

# 🔍 4-daraja: yo'lovchi niyati (kalit so'zlar)
def level_4_check(text):
    passenger_keywords = [
        "1ta odam bor","2ta odam bor","3ta odam bor","4ta odam bor","5ta odam bor",
        "1 ta odam bor","2 ta odam bor","3 ta odam bor","4 ta odam bor","5 ta odam bor",
        "1 kishi bor","2 kishi bor","3 kishi bor","4 kishi bor","5 kishi bor",
        "bitta odam bor","bitta kishi bor","yolg'izman","faqat o'zim","odam bor",
        "odam bilan ketamiz","men bilan odam bor","odam topildi",
        "1 kishi","2 kishi","3 kishi","4 kishi","5 kishi",
        "1ta odam","2ta odam","3ta odam","4ta odam","5ta odam",
        "odam","kishi","taksi kere","1 tamiz","2 tamiz","3 tamiz","4 tamiz","5 tamiz","ketish kerak","1 odam bor","1 kiwi bor"
    ]
    komplekt_keywords = [
        "komplekt odam bor","komplekt bor","komplekt tayyor","komplektmiz",
        "komplekt tayyorman","komplekt yo‘lovchi","komplekt yo‘ldaman","odamlar tayyor",
        "3ta odam tayyor","to‘liq komplekt bor","ketovchi","ketuvchi"
    ]
    intent_keywords = [
        "chiqmoqchiman","chiqdim","yo‘ldaman","tayyorman","hozir chiqaman",
        "hozir yo‘ldaman","bugun ketamiz","ertaga ketamiz","kechqurun chiqamiz",
        "tushda ketaman","hozir ketish kerak","ozgina kutyapman","yo‘lovchi kerak",
        "birga ketamiz","odam qidiryapman","toshkentga boramiz","namanganga boramiz","taxi kerak"
    ]
    location_keywords = [
        "toshkentdan odam bor","toshkentdan chiqamiz","namanganga odam bor",
        "farg‘onaga odam bor","andijonga odam bor","vodiyga odam bor",
        "qo‘qonga odam bor","urganchga odam bor","bekobodga odam bor",
        "angrenga odam bor","gulistonga odam bor","samarqandga odam bor",
        "mawna kerak","mashna kerak","mowna kerak","moshina kerak", "mashina kerak", "moshina kk", "mashina kk",
        "taksi kerak", "taxi kerak", "taksi kk", "taxi kk",
        "moshina qidiryapman", "mashina qidiryapman"
    ]
    contact_keywords = [
        "raqam shu yerda","aloqa raqam","telefon raqam","nomerim shu",
        "menga yozing","telegram raqam","kontaktim","shaxsiy raqam",
        "bog‘laning","aloqaga chiqing","qo‘ng‘iroq qiling","menga telefon qiling","pochta bor"
    ]
    safe_keywords = [
        "ketishim kerak","borishim kerak","yetishim kerak","tez yetishim kerak",
        "yordam kerak","kim bilan boraman","kim bor","kim chiqadi","kim yuradi",
        "chiqishim kerak","chiqmoqchimiz","boramiz","birga chiqamiz","yetib olay",
        "odam kerak emas","haydovchi kerak emas","haydovchisiz boraman",
        "yo‘ldamiz","yo‘lga chiqamiz","yo‘lovchi tayyor","birga ketamiz",
        "kim bor ketadigan","klientman","clientman","klientman 1 kishi","2 klient bor",
        "klient bor","klient tayyor","aka bilan boramiz","opam bilan chiqamiz",
        "duxtirga boramiz","bola bor","ayol bor","farzand bor","ota bilan chiqamiz",
        "onam bilan chiqamiz","xotinim bilan","familamiz bor","kattalar bor",
        "chiqishga tayyor","bugun chiqsam yaxshi bo‘ladi","yurishni niyat qildim"
    ]
    keywords = (passenger_keywords + komplekt_keywords + intent_keywords +
                location_keywords + contact_keywords + safe_keywords)
    return any(k in text for k in keywords)

# 🔍 Yakuniy tekshiruv
def is_valid_order(text):
    t = normalize_text(text)
    if not level_1_check(t): return False
    if not level_2_check(t): return False
    if not level_3_check(t): return False
    if level_4_check(t): return True
    if level_5_check(t) and level_6_check(t): return True
    return False

# 🧭 Maqsad guruhlar
DEST_CHAT_IDS = [
    -1003308279795,
    -1003250099196,
    -1003835270504
]


dest_entities = []  # faqat entity lar saqlanadi


# 📦 Takroriy xabarlar (1 daqiqa ichida)
recent_messages = {}

def is_duplicate(message_text: str, user_id: int) -> bool:
    now = datetime.now()
    key = (user_id, (message_text or "").strip())
    if key in recent_messages:
        if now - recent_messages[key] < timedelta(minutes=1):
            return True
    recent_messages[key] = now
    return False


# 📨 Yangi xabarlar
@client.on(events.NewMessage(chats=SOURCE_CHAT_IDS))
async def handler(event):
    try:
        # bot hali ishga tushmagan bo‘lsa
        if not dest_entities:
            return

        sender = await event.get_sender()
        if not sender or getattr(sender, 'bot', False):
            return

        text = (
            getattr(event.message, 'message', '') or
            getattr(event.message, 'caption', '') or
            ''
        )

        if text and is_duplicate(text, getattr(sender, "id", 0)):
            return

        # 👤 Foydalanuvchi ma’lumotlari
        if isinstance(sender, User):
            full_name = f"{sender.first_name or ''} {sender.last_name or ''}".strip() or "Ismi yo‘q"
            username_mention = f"@{sender.username}" if sender.username else "Yo‘q"
            profile_link = f"https://t.me/{sender.username}" if sender.username else f"tg://user?id={sender.id}"
            account_phone = getattr(sender, 'phone', "Yopiq akkaunt")
        else:
            full_name = "Ismi yo‘q"
            username_mention = "Yo‘q"
            profile_link = "https://t.me/"
            account_phone = "Yopiq akkaunt"

        sana = datetime.now().strftime("%Y-%m-%d")
        vaqt = datetime.now().strftime("%H:%M")
        yo_nalish = extract_direction(text or "")
        group_link = GROUP_LINKS.get(event.chat_id, "#")
        group_tag = group_link.replace("https://t.me/", "@") if group_link.startswith("https://t.me/") else "#"
        phones = re.findall(r'\d{9,}', text or "")
        phone = phones[0] if phones else "Topilmadi"
        msg_link = f"https://t.me/c/{str(event.chat_id)[4:]}/{event.id}"


        # 🎤 Ovozli xabar
        if is_voice_message(event):
            if not os.path.exists("voices"):
                os.makedirs("voices")

            file_path = await client.download_media(
                event.message.media,
                file=f"voices/{event.id}.ogg"
            )

            caption = (
                "━━━━━━━━━━━━━━\n"
                f"📡 Guruh: [{group_tag}]({group_link})\n"
                f"👤 Yozuvchi: [{username_mention}]({profile_link}) ({full_name})\n"
                f"📱 Profil raqam: {account_phone}\n"
                f"📅 Sana: {sana} | ⏰ {vaqt}\n"
                f"📍 Yo‘nalish: {yo_nalish}\n"
                f"🎤 Ovozli zakaz\n"
                f"📝 Havola: [Xabar]({msg_link})\n"
                "━━━━━━━━━━━━━━"
            )

            for ent in dest_entities:
                await client.send_file(
                    ent,
                    file_path,
                    caption=caption,
                    parse_mode="markdown"
                )

            try:
                os.remove(file_path)
            except Exception:
                pass
            return


        # 🧾 Matnli xabar filtri
        if not is_valid_order(text or ""):
            return

        formatted = (
            "━━━━━━━━━━━━━━\n"
            f"📡 Guruh: [{group_tag}]({group_link})\n"
            f"👤 Yozuvchi: [{username_mention}]({profile_link}) ({full_name})\n"
            f"📱 Profil raqam: {account_phone}\n"
            f"📅 Sana: {sana} | ⏰ {vaqt}\n"
            f"📍 Yo‘nalish: {yo_nalish}\n"
            f"💬 Xabar: {text}\n"
            f"📞 Aloqa: {phone}\n"
            f"📝 Havola: [Xabar]({msg_link})\n"
            "━━━━━━━━━━━━━━"
        )

        # ✅ 4 ta guruhga yuborish
        for ent in dest_entities:
            await client.send_message(
                ent,
                formatted,
                parse_mode="markdown"
            )

    except Exception as e:
        print("❌ Xatolik:", e)
        traceback.print_exc()


# ▶️ Botni ishga tushirish
async def main():
    print("🚀 Bot ishga tushmoqda...")
    await client.start()

    # target guruhlarni entity ga aylantirish
    for cid in DEST_CHAT_IDS:
        ent = await client.get_entity(cid)
        dest_entities.append(ent)

    print("✅ Telegramga ulandi. Xabarlar kutilyapti...")
    await client.run_until_disconnected()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
