"""
Download free images for Staff / Product records that have no image.

Uses loremflickr.com (CC-licensed Flickr images) — no API key required.
Falls back to picsum.photos if loremflickr fails.

Usage:
    python manage.py download_missing_images          # dry-run (show what would be downloaded)
    python manage.py download_missing_images --execute # actually download & save
"""
import io
import time
import logging

import requests
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from booking.models import Staff, Product

logger = logging.getLogger(__name__)

# ── Search-keyword mappings ──────────────────────────────────────────

STAFF_KEYWORDS = {
    # id: (english_keywords, filename_prefix)
    1:  ("japanese man barista cafe",                  "staff-admin"),
    2:  ("fortune teller woman mystic",                "staff-fortuneteller"),
    3:  ("japanese man store manager",                 "staff-manager"),
    4:  ("japanese woman cafe staff apron",            "staff-01"),
    22: ("business owner man suit",                    "staff-demo-owner"),
    23: ("store manager woman professional",           "staff-demo-manager"),
    24: ("cafe staff woman service",                   "staff-demo-staff"),
    25: ("developer man laptop coding",                "staff-demo-dev"),
    26: ("fortune teller tarot cards woman",           "staff-demo-fortune"),
    27: ("mystical woman portrait moon star",          "staff-hoshino-luna"),
    28: ("elegant japanese woman lantern night",       "staff-tsukimi-akari"),
    29: ("young woman barista coffee",                 "staff-minase-sora"),
    30: ("spiritual woman incense meditation",         "staff-asagiri-hikaru"),
}

PRODUCT_KEYWORDS = {
    # id: (english_keywords, filename_prefix)
    # ── Shisha ──
    117: ("hookah shisha custom mix smoke",             "sh-custom-mix"),
    113: ("watermelon mint drink fresh green",          "sh-watermelon-mint"),
    114: ("chai spice cinnamon warm drink",             "sh-chai-spice"),
    116: ("chocolate mint dessert dark green",          "sh-choco-mint"),
    112: ("mango tropical fruit yellow",                "sh-mango"),
    115: ("rose flower pink elegant",                   "sh-rose"),
    # ── Drinks ──
    104: ("cassis orange cocktail bar",                 "dr-cassis-orange"),
    100: ("chai tea latte cup warm",                    "dr-chai-tea"),
    105: ("highball whisky soda drink bar",             "dr-highball"),
    101: ("chamomile herbal tea cup",                   "dr-chamomile"),
    102: ("draft beer glass pub bar",                   "dr-beer"),
    103: ("lemon sour cocktail citrus",                 "dr-lemon-sour"),
    # ── Food ──
    110: ("acai bowl fruit berry healthy",              "fd-acai-bowl"),
    108: ("chocolate cake dessert slice",               "fd-choco-cake"),
    109: ("cheesecake slice cream dessert",             "fd-cheesecake"),
    106: ("french fries golden crispy potato",          "fd-fries"),
    107: ("mixed nuts almonds cashew bowl",             "fd-mixed-nuts"),
    111: ("edamame beans japanese green",               "fd-edamame"),
}


def download_image(keywords, width=640, height=480, retries=2):
    """Download a CC-licensed image from loremflickr matching *keywords*.

    Returns (bytes, content_type) or (None, None) on failure.
    """
    # loremflickr: random Flickr image matching keywords
    search = ",".join(keywords.split()[:3])  # use first 3 words
    url = f"https://loremflickr.com/{width}/{height}/{search}"

    for attempt in range(retries + 1):
        try:
            resp = requests.get(url, timeout=15, allow_redirects=True)
            if resp.status_code == 200 and len(resp.content) > 1000:
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

    def handle(self, *args, **options):
        execute = options["execute"]
        mode = "EXECUTE" if execute else "DRY-RUN"
        self.stdout.write(f"\n=== download_missing_images [{mode}] ===\n")

        # ── Staff ──
        staff_qs = Staff.objects.filter(thumbnail="").order_by("id")
        self.stdout.write(f"\nStaff without images: {staff_qs.count()}")
        for s in staff_qs:
            kw_entry = STAFF_KEYWORDS.get(s.id)
            if not kw_entry:
                self.stdout.write(f"  SKIP id={s.id} {s.name} (no keyword mapping)")
                continue
            keywords, prefix = kw_entry
            self.stdout.write(f"  id={s.id} {s.name} -> search: '{keywords}'")

            if execute:
                data, ct = download_image(keywords, 400, 400)
                if data:
                    ext = ext_from_ct(ct)
                    filename = f"{prefix}{ext}"
                    s.thumbnail.save(filename, ContentFile(data), save=True)
                    self.stdout.write(
                        self.style.SUCCESS(f"    SAVED: {s.thumbnail.name} ({len(data)} bytes)")
                    )
                else:
                    self.stdout.write(self.style.ERROR(f"    FAILED to download"))
                time.sleep(0.5)  # rate limit

        # ── Products ──
        product_qs = Product.objects.filter(image="").order_by("id")
        self.stdout.write(f"\nProducts without images: {product_qs.count()}")
        for p in product_qs:
            kw_entry = PRODUCT_KEYWORDS.get(p.id)
            if not kw_entry:
                self.stdout.write(f"  SKIP id={p.id} {p.name} (no keyword mapping)")
                continue
            keywords, prefix = kw_entry
            self.stdout.write(f"  id={p.id} {p.name} -> search: '{keywords}'")

            if execute:
                data, ct = download_image(keywords, 640, 480)
                if data:
                    ext = ext_from_ct(ct)
                    filename = f"{prefix}{ext}"
                    p.image.save(filename, ContentFile(data), save=True)
                    self.stdout.write(
                        self.style.SUCCESS(f"    SAVED: {p.image.name} ({len(data)} bytes)")
                    )
                else:
                    self.stdout.write(self.style.ERROR(f"    FAILED to download"))
                time.sleep(0.5)

        self.stdout.write(self.style.SUCCESS("\nDone!"))
