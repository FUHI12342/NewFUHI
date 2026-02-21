from django.contrib import admin
from django.contrib.admin.sites import AdminSite
from .models import Staff
import logging

logger = logging.getLogger(__name__)

def get_user_role(request):
    if not request.user.is_authenticated:
        return 'none'
    if request.user.is_superuser:
        return 'superuser'
    staff = Staff.objects.filter(user=request.user).select_related("store").first()
    if staff:
        if staff.is_developer:
            return 'developer'
        elif staff.is_store_manager:
            return 'manager'
        else:
            return 'staff'
    return 'none'

class RoleBasedAdminSite(AdminSite):
    def get_app_list(self, request, app_label=None):
        role = get_user_role(request)
        logger.info(f"get_app_list: user={request.user.username if request.user.is_authenticated else 'anon'}, is_staff={request.user.is_staff if request.user.is_authenticated else False}, is_superuser={request.user.is_superuser if request.user.is_authenticated else False}, role={role}, app_label={app_label}")
        if role == 'superuser' or role == 'developer':
            app_list = super().get_app_list(request, app_label)
            logger.info(f"superuser/developer app_list: {[app['name'] for app in app_list]}")
            return app_list
        app_list = super().get_app_list(request, app_label)
        if role == 'manager':
            allowed_models = ['schedule', 'order', 'orderitem', 'staff', 'store', 'iotdevice', 'iotevent', 'category', 'product', 'producttranslation', 'stockmovement', 'property', 'propertydevice', 'propertyalert', 'systemconfig']
        elif role == 'staff':
            allowed_models = ['schedule', 'order', 'orderitem', 'staff', 'iotdevice', 'iotevent', 'product', 'stockmovement']
        else:
            allowed_models = ['schedule', 'order', 'orderitem']

        filtered = []
        for app in app_list:
            models = [m for m in app['models'] if m['object_name'].lower() in allowed_models]
            if models:
                app_copy = app.copy()
                app_copy['models'] = models
                filtered.append(app_copy)
        result = filtered
        logger.info(f"filtered app_list: {[app['name'] for app in result]}")
        return result


custom_site = RoleBasedAdminSite(name="admin")


