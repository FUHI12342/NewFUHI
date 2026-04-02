"""IoT admin: IoTDevice, IoTEvent, IRCode, VentilationAutoControl, Property."""
import json

from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from ..admin_site import custom_site
from ..models import (
    IoTDevice, IoTEvent, IRCode, VentilationAutoControl,
    Property, PropertyDevice, PropertyAlert,
    SystemConfig,
)


class IoTEventInline(admin.TabularInline):
    model = IoTEvent
    extra = 0
    readonly_fields = ('created_at',)
    max_num = 50


class IRCodeInline(admin.TabularInline):
    model = IRCode
    extra = 0
    readonly_fields = ('created_at',)
    fields = ('name', 'protocol', 'code', 'address', 'command', 'created_at')


class IoTDeviceAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'store',
        'device_type',
        'external_id',
        'is_active',
        'last_seen_at',
        'mq9_threshold',
        'alert_enabled',
        'alert_email',
        'alert_line_user_id',
        'wifi_ssid',
    )

    search_fields = ('name', 'external_id', 'store__name')
    readonly_fields = ('last_seen_at',)
    list_per_page = 10
    ordering = ('store', 'name')
    inlines = [IoTEventInline, IRCodeInline]


class IoTEventAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'event_type', 'mq9_value', 'device', 'sensor_summary')

    search_fields = ('device__name', 'device__external_id')
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    list_per_page = 10

    def sensor_summary(self, obj):
        if not obj.payload:
            return "-"
        try:
            data = json.loads(obj.payload)
        except (json.JSONDecodeError, TypeError, ValueError):
            return obj.payload[:50] + "..." if len(obj.payload) > 50 else obj.payload

        keys = ["mq9", "light", "sound", "temp", "hum"]
        parts = []
        for k in keys:
            if k in data and data[k] is not None:
                label = {"mq9": "CO", "light": "光", "sound": "音", "temp": "温度", "hum": "湿度"}[k]
                parts.append(f"{label}: {data[k]}")
        return " / ".join(parts) if parts else "-"

    sensor_summary.short_description = _("センサー要約")
    sensor_summary.admin_order_field = 'event_type'


class IRCodeAdmin(admin.ModelAdmin):
    list_display = ('name', 'device', 'protocol', 'code', 'pulse_count', 'created_at')

    search_fields = ('name', 'device__name', 'code')
    readonly_fields = ('created_at', 'pulse_count')
    list_per_page = 10
    ordering = ('device', 'name')
    actions = ['send_ir_code']

    def pulse_count(self, obj):
        if obj.raw_data:
            try:
                data = json.loads(obj.raw_data)
                if isinstance(data, list):
                    return len(data)
            except (json.JSONDecodeError, TypeError):
                pass
        return '-'
    pulse_count.short_description = _('パルス数')

    @admin.action(description=_('IRコードを送信'))
    def send_ir_code(self, request, queryset):
        import json as _json
        count = 0
        for ir_code in queryset:
            device = ir_code.device
            cmd = {
                'action': 'send_ir',
                'protocol': ir_code.protocol,
            }
            if ir_code.protocol == 'RAW' and ir_code.raw_data:
                cmd['raw_data'] = ir_code.raw_data
            else:
                cmd['code'] = ir_code.code
            device.pending_ir_command = _json.dumps(cmd)
            device.save(update_fields=['pending_ir_command'])
            count += 1
        self.message_user(request, f'{count} 件のIRコード送信をキューしました。')


class VentilationAutoControlAdmin(admin.ModelAdmin):
    list_display = ('name', 'device', 'is_active', 'threshold_on', 'threshold_off',
                    'consecutive_count', 'fan_state', 'last_on_at', 'last_off_at')
    list_filter = ('is_active', 'fan_state')
    readonly_fields = ('fan_state', 'last_on_at', 'last_off_at')
    list_per_page = 10
    ordering = ('name',)
    fieldsets = (
        (_('基本設定'), {'fields': ('device', 'name', 'is_active')}),
        (_('閾値設定'), {
            'fields': ('threshold_on', 'threshold_off', 'consecutive_count', 'cooldown_seconds'),
            'description': _('MQ-9の生ADC値で設定。平常時≒200-250、CO検出時は上昇。'),
        }),
        (_('SwitchBot設定'), {'fields': ('switchbot_token', 'switchbot_secret', 'switchbot_device_id')}),
        (_('状態（自動更新）'), {'fields': ('fan_state', 'last_on_at', 'last_off_at')}),
    )

    def save_model(self, request, obj, form, change):
        if 'switchbot_token' in form.changed_data:
            obj.set_switchbot_token(form.cleaned_data['switchbot_token'])
        if 'switchbot_secret' in form.changed_data:
            obj.set_switchbot_secret(form.cleaned_data['switchbot_secret'])
        super().save_model(request, obj, form, change)


class SystemConfigAdmin(admin.ModelAdmin):
    list_display = ('key', 'value', 'updated_at')
    search_fields = ('key', 'value')
    readonly_fields = ('updated_at',)
    list_per_page = 10
    ordering = ('key',)


class PropertyDeviceInline(admin.TabularInline):
    model = PropertyDevice
    extra = 0
    autocomplete_fields = ('device',)


class PropertyAlertInline(admin.TabularInline):
    model = PropertyAlert
    extra = 0
    readonly_fields = ('created_at',)


class PropertyAdmin(admin.ModelAdmin):
    list_display = ('name', 'address', 'property_type', 'owner_name', 'store', 'is_active')

    search_fields = ('name', 'address', 'owner_name')
    list_per_page = 10
    ordering = ('name',)
    inlines = [PropertyDeviceInline, PropertyAlertInline]


# Registration
custom_site.register(IoTDevice, IoTDeviceAdmin)
custom_site.register(VentilationAutoControl, VentilationAutoControlAdmin)
custom_site.register(SystemConfig, SystemConfigAdmin)
custom_site.register(Property, PropertyAdmin)
