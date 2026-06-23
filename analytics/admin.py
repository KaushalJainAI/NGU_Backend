from django.contrib import admin

from .models import UserEvent, UserGeo


@admin.register(UserEvent)
class UserEventAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'event_type', 'product', 'category', 'query', 'created_at')
    list_filter = ('event_type', 'created_at')
    search_fields = ('user__email', 'query')
    raw_id_fields = ('user', 'product', 'combo', 'category')
    date_hierarchy = 'created_at'


@admin.register(UserGeo)
class UserGeoAdmin(admin.ModelAdmin):
    list_display = ('user', 'city', 'state', 'pincode_prefix', 'updated_at')
    list_filter = ('state',)
    search_fields = ('user__email', 'city', 'state', 'pincode_prefix')
    raw_id_fields = ('user',)
