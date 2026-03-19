"""
Download free images for Staff / Product records that have no image.

Uses loremflickr.com (CC-licensed Flickr images) — no API key required.
Falls back to picsum.photos if loremflickr fails.

Usage:
    python manage.py download_missing_images          # dry-run (show what would be downloaded)
    python manage.py download_missing_images --execute # actually download & save
"""
import time
import logging

import requests
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from booking.models import Staff, Product

logger = logging.getLogger(__name__)

# ── Search-keyword mappings (by name, not ID) ──────────────────────

STAFF_KEYWORDS = {
    # name: (english_keywords, filename_prefix)
    "admin":       ("man portrait professional headshot",     "staff-admin"),
    "owner":       ("fortune teller woman mystic tarot",      "staff-fortuneteller"),
    "manager":     ("japanese man store manager",             "staff-manager"),
    "staff01":     ("japanese woman cafe staff apron",        "staff-01"),
    "デモ オーナー":  ("man suit portrait business",            "staff-demo-owner"),
    "デモ 店長":     ("store manager woman professional",      "staff-demo-manager"),
    "デモ スタッフ":  ("cafe staff woman service apron",        "staff-demo-staff"),
    "デモ 開発者":   ("man computer programming office",       "staff-demo-dev"),
    "デモ 占い師":   ("fortune teller tarot cards woman",      "staff-demo-fortune"),
    "星野 ルナ":     ("mystical woman portrait moon star",     "staff-hoshino-luna"),
    "月見 アカリ":   ("elegant japanese woman lantern night",  "staff-tsukimi-akari"),
    "水瀬 ソラ":     ("barista woman coffee portrait smile",   "staff-minase-sora"),
    "朝霧 ヒカル":   ("spiritual woman incense meditation",    "staff-asagiri-hikaru"),
}

PRODUCT_KEYWORDS = {
    # name: (english_keywords, filename_prefix)
    # ── Shisha ──
    "カスタムMIX":              ("hookah smoke lounge",                    "sh-custom-mix"),
    "スイカミント":             ("watermelon mint drink fresh green",       "sh-watermelon-mint"),
    "チャイスパイス":           ("chai spice cinnamon warm drink",          "sh-chai-spice"),
    "チョコミント":             ("chocolate mint dessert dark green",       "sh-choco-mint"),
    "マンゴー":                 ("mango tropical fruit yellow",             "sh-mango"),
    "ローズ":                   ("rose flower pink elegant",                "sh-rose"),
    # ── Drinks ──
    "カシスオレンジ":           ("orange juice cocktail glass",             "dr-cassis-orange"),
    "ハイボール":               ("whisky glass ice drink",                  "dr-highball"),
    "ハーブティー（カモミール）": ("chamomile herbal tea cup",               "dr-chamomile"),
    "ビール（生）":             ("draft beer glass pub bar",                "dr-beer"),
    "レモンサワー":             ("lemon sour cocktail citrus",              "dr-lemon-sour"),
    # ── Food ──
    "アサイーボウル":           ("acai bowl fruit berry healthy",            "fd-acai-bowl"),
    "チョコレートケーキ":       ("chocolate cake dessert slice",             "fd-choco-cake"),
    "チーズケーキ":             ("cheesecake slice cream dessert",           "fd-cheesecake"),
    "フライドポテト":           ("french fries golden crispy potato",        "fd-fries"),
    "枝豆":                     ("edamame beans japanese green",             "fd-edamame"),
}

# Special handling: "チャイティー" and "ミックスナッツ" have duplicates (one with image, one without).
# We only target records without images, so the duplicate name is fine.
PRODUCT_KEYWORDS_DUPLICATES = {
    "チャイティー":  ("chai tea latte cup warm",              "dr-chai-tea"),
    "ミックスナッツ": ("mixed nuts almonds cashew bowl",      "fd-mixed-nuts"),
}


def download_image(keywords, width=640, height=480, retries=2):
    """Download a CC-licensed image from loremflickr matching *keywords*.

    Returns (bytes, content_type) or (None, None) on failure.
    """
    search = ",".join(keywords.split()[:3])
    url = f"https://loremflickr.com/{width}/{height}/{search}"

    for attempt in range(retries + 1):
        try:
            resp = requests.get(url, timeout=15, allow_redirects=True)
            if resp.status_code == 200 and len(resp.content) > 1000:
                # Skip loremflickr default placeholder
                if "defaultImage" in resp.url:
                    logger.info("Got default placeholder for '%s', retrying", keywords)
                    time.sleep(1)
                    continue
                ct = resp.headers.get("Content-Type", "image/jpeg")
                return resp.content, ct
        except requests.RequestException as exc:
            logger.warning("loremflickr attempt %d failed: %s", attempt, exc)
        time.sleep(1)

    # Fallback: picsum.photos (random, not keyword-matched)
    try:
        resp = requests.get(
            f"https://picsum.photos/{width}/{height}",
            timeout=15,
            allow_redirects=True,
        )
        if resp.status_code == 200 and len(resp.content) > 1000:
            return resp.content, "image/jpeg"
    except requests.RequestException:
        pass

    return None, None


def ext_from_ct(content_type):
    """Map Content-Type to file extension."""
    mapping = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }
    return mapping.get(content_type, ".jpg")


class Command(BaseCommand):
    help = "Download free images for Staff/Product records without images."

    def add_arguments(self, parser):
        parser.add_argument(
            "--execute",
            action="store_true",
            help="Actually download and save (default is dry-run).",
        )

    def _save_image(self, obj, field_name, keywords, prefix, size, execute):
        """Download and save image for a model instance."""
        self.stdout.write(f"  id={obj.id} {obj.name} -> search: '{keywords}'")
        if not execute:
            return

        w, h = size
        data, ct = download_image(keywords, w, h)
        if data:
            ext = ext_from_ct(ct)
            filename = f"{prefix}{ext}"
            getattr(obj, field_name).save(filename, ContentFile(data), save=True)
            self.stdout.write(
                self.style.SUCCESS(
                    f"    SAVED: {getattr(obj, field_name).name} ({len(data)} bytes)"
                )
            )
        else:
            self.stdout.write(self.style.ERROR("    FAILED to download"))
        time.sleep(0.5)

    def handle(self, *args, **options):
        execute = options["execute"]
        mode = "EXECUTE" if execute else "DRY-RUN"
        self.stdout.write(f"\n=== download_missing_images [{mode}] ===\n")

        # ── Staff (matched by name) ──
        staff_qs = Staff.objects.filter(thumbnail="").order_by("id")
        self.stdout.write(f"\nStaff without images: {staff_qs.count()}")
        for s in staff_qs:
            kw_entry = STAFF_KEYWORDS.get(s.name)
            if not kw_entry:
                self.stdout.write(f"  SKIP id={s.id} {s.name} (no keyword mapping)")
                continue
            keywords, prefix = kw_entry
            self._save_image(s, "thumbnail", keywords, prefix, (400, 400), execute)

        # ── Products (matched by name) ──
        product_qs = Product.objects.filter(image="").order_by("id")
        self.stdout.write(f"\nProducts without images: {product_qs.count()}")
        for p in product_qs:
            kw_entry = PRODUCT_KEYWORDS.get(p.name)
            if not kw_entry:
                kw_entry = PRODUCT_KEYWORDS_DUPLICATES.get(p.name)
            if not kw_entry:
                self.stdout.write(f"  SKIP id={p.id} {p.name} (no keyword mapping)")
                continue
            keywords, prefix = kw_entry
            self._save_image(p, "image", keywords, prefix, (640, 480), execute)

        self.stdout.write(self.style.SUCCESS("\nDone!"))
