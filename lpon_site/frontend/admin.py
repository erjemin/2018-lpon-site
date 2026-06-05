# Кастомная конфигурация Django Admin для LPON сайта.
# Регистрируем модели с удобным интерфейсом.

from django.contrib import admin
from django.contrib.auth.models import User, Group
from .models import (
    TbImage, TbArticle, TbArtist, TbItem, TbLabel, TbSeller,
    TbOffer, TbSource, TbOfferHistory, TbMusicStyle, TbFormat
)

# ============================================================================
# ModelAdmin классы для каждой модели
# ============================================================================
class ImageAdmin(admin.ModelAdmin):
    """Админ для изображений"""
    list_display = ('id', 'l_img_source', 'l_img_reality', 'i_img_sort', 't_img_created')
    list_filter = ('l_img_source', 'l_img_reality', 't_img_created')
    ordering = ('-t_img_created', 'i_img_sort')
    readonly_fields = ('t_img_created', 't_img_updated')


class ArticleAdmin(admin.ModelAdmin):
    """Админ для статей"""
    list_display = ('id', 's_article_title', 'l_article_type', 'b_article_published', 't_article_created')
    list_filter = ('l_article_type', 'b_article_published', 't_article_created')
    search_fields = ('s_article_title', 'slug')
    prepopulated_fields = {'slug': ('s_article_title',)}
    readonly_fields = ('t_article_created', 't_article_updated')
    filter_horizontal = ('k_article_to_styles',)


class MusicStyleAdmin(admin.ModelAdmin):
    """Админ для музыкальных стилей"""
    list_display = ('id', 's_style_name', 's_style_slug')
    search_fields = ('s_style_name', 's_style_slug')
    readonly_fields = ('s_style_slug',)


class FormatAdmin(admin.ModelAdmin):
    """Админ для форматов"""
    list_display = ('id', 's_format', 's_format_slug')
    search_fields = ('s_format',)
    readonly_fields = ('s_format_slug',)


class ArtistAdmin(admin.ModelAdmin):
    """Админ для артистов"""
    list_display = ('id', 's_artist', 't_artist_created')
    search_fields = ('s_artist',)
    readonly_fields = ('t_artist_created', 't_artist_updated')


class ItemAdmin(admin.ModelAdmin):
    """Админ для товаров"""
    list_display = ('id', 's_item', 't_item_date', 't_item_created')
    list_filter = ('t_item_date', 't_item_created')
    search_fields = ('s_item',)
    filter_horizontal = ('k_item_to_artist',)
    readonly_fields = ('t_item_created', 't_item_updated')


class LabelAdmin(admin.ModelAdmin):
    """Админ для лейблов"""
    list_display = ('id', 's_label', 't_label_created')
    search_fields = ('s_label',)
    readonly_fields = ('t_label_created', 't_label_updated')


class SellerAdmin(admin.ModelAdmin):
    """Админ для продавцов"""
    list_display = ('id', 's_seller', 'l_seller_type', 't_seller_created')
    list_filter = ('l_seller_type',)
    search_fields = ('s_seller',)
    readonly_fields = ('t_seller_created', 't_seller_updated')


class SourceAdmin(admin.ModelAdmin):
    """Админ для источников"""
    list_display = ('id', 's_source_name', 'k_source_to_seller', 'l_source_type', 'l_source_currency', 't_source_data')
    list_filter = ('l_source_type', 'l_source_currency', 't_source_data')
    search_fields = ('s_source_name',)
    readonly_fields = ('t_source_created', 't_source_updated')


class OfferAdmin(admin.ModelAdmin):
    """Админ для предложений"""
    list_display = ('id', 's_offer', 'k_offer_to_item', 'f_offer_price', 'i_offer_quantity', 'i_offer_views')
    list_filter = ('l_offer_condition_media', 'l_offer_condition_sleeve', 't_offer_created')
    search_fields = ('s_offer',)
    filter_horizontal = ('k_offer_to_format', 'k_offer_to_image')
    readonly_fields = ('s_offer_skip32', 't_offer_created', 't_offer_updated', 'i_offer_views', 'i_offer_favorites')


class OfferHistoryAdmin(admin.ModelAdmin):
    """Админ для истории изменений офферов"""
    list_display = ('id', 'k_history_to_offer', 'f_history_price', 'i_history_quantity', 't_history_created')
    list_filter = ('t_history_created',)
    readonly_fields = ('t_history_created',)


# ============================================================================
# Регистрация моделей в дефолтном admin.site
# ============================================================================
admin.site.register(TbImage, ImageAdmin)
admin.site.register(TbArticle, ArticleAdmin)
admin.site.register(TbMusicStyle, MusicStyleAdmin)
admin.site.register(TbFormat, FormatAdmin)
admin.site.register(TbArtist, ArtistAdmin)
admin.site.register(TbItem, ItemAdmin)
admin.site.register(TbLabel, LabelAdmin)
admin.site.register(TbSeller, SellerAdmin)
admin.site.register(TbSource, SourceAdmin)
admin.site.register(TbOffer, OfferAdmin)
admin.site.register(TbOfferHistory, OfferHistoryAdmin)

# User и Group уже зарегистрированы auth приложением

# ============================================================================
# Кастомизация админ-сайта через ready() в apps.py (переименование через verbose_name)
# ============================================================================



