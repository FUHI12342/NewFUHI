"""CO閾値連動 換気扇自動制御 (SwitchBot スマートプラグ)"""

import base64
import hashlib
import hmac
import json
import logging
import time
import uuid

import requests
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

SWITCHBOT_API_BASE = "https://api.switch-bot.com/v1.1"


def _switchbot_headers(token: str, secret: str) -> dict:
    """SwitchBot API v1.1 HMAC-SHA256 署名ヘッダー生成"""
    t = str(int(time.time() * 1000))
    nonce = uuid.uuid4().hex
    string_to_sign = f"{token}{t}{nonce}"
    sign = base64.b64encode(
        hmac.new(
            secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            hashlib.sha256,
        ).digest()
    ).decode("utf-8")
    return {
        "Authorization": token,
        "sign": sign,
        "t": t,
        "nonce": nonce,
        "Content-Type": "application/json",
    }


def switchbot_command(token: str, secret: str, device_id: str, command: str) -> dict:
    """SwitchBot デバイスにコマンド送信 (turnOn / turnOff)"""
    url = f"{SWITCHBOT_API_BASE}/devices/{device_id}/commands"
    headers = _switchbot_headers(token, secret)
    payload = {
        "command": command,
        "parameter": "default",
        "commandType": "command",
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    logger.info("SwitchBot %s -> %s: %s", device_id, command, data)
    return data


def check_ventilation_rules(device, mq9_value: float) -> None:
    """
    IoTEvent 保存後に呼ばれる。
    device に紐づくアクティブな VentilationAutoControl を取得し、
    直近N件の mq9_value を確認して ON/OFF を判定・実行する。
    """
    from .models import IoTEvent, VentilationAutoControl

    with transaction.atomic():
        rules = VentilationAutoControl.objects.select_for_update().filter(
            device=device, is_active=True
        )
        if not rules.exists():
            return

        now = timezone.now()

        for rule in rules:
            # クールダウン判定 (use the most recent action timestamp)
            last_action = max(filter(None, [rule.last_on_at, rule.last_off_at]), default=None)
            if last_action:
                elapsed = (now - last_action).total_seconds()
                if elapsed < rule.cooldown_seconds:
                    logger.debug(
                        "Ventilation rule %s: cooldown (%ds remaining)",
                        rule.name,
                        rule.cooldown_seconds - elapsed,
                    )
                    continue

            # ON 判定: 現在値が閾値以上 → 直近N件を確認
            if mq9_value >= rule.threshold_on and rule.fan_state != "on":
                recent_values = list(
                    IoTEvent.objects.filter(device=device, mq9_value__isnull=False)
                    .order_by("-created_at")
                    .values_list("mq9_value", flat=True)[: rule.consecutive_count]
                )
                if (
                    len(recent_values) >= rule.consecutive_count
                    and all(v >= rule.threshold_on for v in recent_values)
                ):
                    logger.info(
                        "Ventilation ON triggered: rule=%s, values=%s",
                        rule.name,
                        recent_values,
                    )
                    try:
                        switchbot_command(
                            rule.get_switchbot_token(),
                            rule.get_switchbot_secret(),
                            rule.switchbot_device_id,
                            "turnOn",
                        )
                        rule.fan_state = "on"
                        rule.last_on_at = now
                        rule.save(update_fields=["fan_state", "last_on_at"])
                    except Exception:
                        logger.exception(
                            "SwitchBot turnOn failed for rule=%s, device=%s. "
                            "Applying cooldown to prevent infinite retries.",
                            rule.name, rule.switchbot_device_id,
                        )
                        # Apply cooldown even on failure to prevent rapid retries
                        rule.last_on_at = now
                        rule.save(update_fields=["last_on_at"])

            # OFF 判定: 現在値が閾値以下 & 現在ON
            elif mq9_value <= rule.threshold_off and rule.fan_state == "on":
                logger.info(
                    "Ventilation OFF triggered: rule=%s, mq9=%.1f <= %d",
                    rule.name,
                    mq9_value,
                    rule.threshold_off,
                )
                try:
                    switchbot_command(
                        rule.get_switchbot_token(),
                        rule.get_switchbot_secret(),
                        rule.switchbot_device_id,
                        "turnOff",
                    )
                    rule.fan_state = "off"
                    rule.last_off_at = now
                    rule.save(update_fields=["fan_state", "last_off_at"])
                except Exception:
                    logger.exception(
                        "SwitchBot turnOff failed for rule=%s, device=%s. "
                        "Applying cooldown to prevent infinite retries.",
                        rule.name, rule.switchbot_device_id,
                    )
                    # Apply cooldown even on failure to prevent rapid retries
                    rule.last_off_at = now
                    rule.save(update_fields=["last_off_at"])
