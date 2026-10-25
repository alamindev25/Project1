from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache

from apps.cms.models import CMS, FAQ
from apps.system_setting.models import (
    AboutSystem,
    LandingPageHero, LandingPagePricing, LandingPageFeature, 
    LandingPageBadge, DashboardSettings, LandingPageSection,
    LandingPreviewSample, LandingTestimonial, LandingCheckoutBrand
)
from .models import TemplateCategory, DocumentFeedback


def clear_landing_cache():
    """Clear landing page cache (safe - fails silently if Redis unavailable)"""
    try:
        cache.delete_many(['landing_page_data', 'landing_page_data_v8', 'landing_page_data_v9', 'landing_page_data_v10', 'landing_page_data_v11', 'landing_page_data_v12', 'landing_page_data_v13'])
    except Exception:
        # Redis connection failed, continue silently
        pass


# Landing Page Hero Section Signals
@receiver(post_save, sender=LandingPageHero)
def clear_landing_cache_on_hero_change(sender, instance, **kwargs):
    """Clear cache when hero section is saved"""
    clear_landing_cache()


@receiver(post_delete, sender=LandingPageHero)
def clear_landing_cache_on_hero_delete(sender, instance, **kwargs):
    """Clear cache when hero section is deleted"""
    clear_landing_cache()


# Landing Page Pricing Signals
@receiver(post_save, sender=LandingPagePricing)
def clear_landing_cache_on_pricing_change(sender, instance, **kwargs):
    """Clear cache when pricing is changed"""
    clear_landing_cache()


@receiver(post_delete, sender=LandingPagePricing)
def clear_landing_cache_on_pricing_delete(sender, instance, **kwargs):
    """Clear cache when pricing is deleted"""
    clear_landing_cache()


# Landing Page Feature Signals
@receiver(post_save, sender=LandingPageFeature)
def clear_landing_cache_on_feature_change(sender, instance, **kwargs):
    """Clear cache when feature is changed"""
    clear_landing_cache()


@receiver(post_delete, sender=LandingPageFeature)
def clear_landing_cache_on_feature_delete(sender, instance, **kwargs):
    """Clear cache when feature is deleted"""
    clear_landing_cache()


# Landing Page Badge Signals
@receiver(post_save, sender=LandingPageBadge)
def clear_landing_cache_on_badge_change(sender, instance, **kwargs):
    """Clear cache when badge is changed"""
    clear_landing_cache()


@receiver(post_delete, sender=LandingPageBadge)
def clear_landing_cache_on_badge_delete(sender, instance, **kwargs):
    """Clear cache when badge is deleted"""
    clear_landing_cache()


# Template Category Signals
@receiver(post_save, sender=TemplateCategory)
def clear_landing_cache_on_category_change(sender, instance, **kwargs):
    """Clear landing page cache when a TemplateCategory is saved"""
    clear_landing_cache()


@receiver(post_delete, sender=TemplateCategory)
def clear_landing_cache_on_category_delete(sender, instance, **kwargs):
    """Clear landing page cache when a TemplateCategory is deleted"""
    clear_landing_cache()


# FAQ Signals
@receiver(post_save, sender=FAQ)
def clear_landing_cache_on_faq_change(sender, instance, **kwargs):
    """Clear landing page cache when an FAQ is saved"""
    clear_landing_cache()


@receiver(post_delete, sender=FAQ)
def clear_landing_cache_on_faq_delete(sender, instance, **kwargs):
    """Clear landing page cache when an FAQ is deleted"""
    clear_landing_cache()


# CMS Blocks Signals
@receiver(post_save, sender=CMS)
def clear_landing_cache_on_cms_change(sender, instance, **kwargs):
    """Clear landing page cache when CMS block content is changed."""
    clear_landing_cache()


@receiver(post_delete, sender=CMS)
def clear_landing_cache_on_cms_delete(sender, instance, **kwargs):
    """Clear landing page cache when CMS block content is deleted."""
    clear_landing_cache()


# Landing Page Section Signals
@receiver(post_save, sender=LandingPageSection)
def clear_landing_cache_on_section_change(sender, instance, **kwargs):
    """Clear landing page cache when a landing section is changed."""
    clear_landing_cache()


@receiver(post_delete, sender=LandingPageSection)
def clear_landing_cache_on_section_delete(sender, instance, **kwargs):
    """Clear landing page cache when a landing section is deleted."""
    clear_landing_cache()


@receiver(post_save, sender=LandingPreviewSample)
def clear_landing_cache_on_preview_sample_change(sender, instance, **kwargs):
    clear_landing_cache()


@receiver(post_delete, sender=LandingPreviewSample)
def clear_landing_cache_on_preview_sample_delete(sender, instance, **kwargs):
    clear_landing_cache()


@receiver(post_save, sender=LandingTestimonial)
def clear_landing_cache_on_testimonial_change(sender, instance, **kwargs):
    clear_landing_cache()


@receiver(post_delete, sender=LandingTestimonial)
def clear_landing_cache_on_testimonial_delete(sender, instance, **kwargs):
    clear_landing_cache()


@receiver(post_save, sender=LandingCheckoutBrand)
def clear_landing_cache_on_checkout_brand_change(sender, instance, **kwargs):
    clear_landing_cache()


@receiver(post_delete, sender=LandingCheckoutBrand)
def clear_landing_cache_on_checkout_brand_delete(sender, instance, **kwargs):
    clear_landing_cache()


@receiver(post_save, sender=DocumentFeedback)
def clear_landing_cache_on_document_feedback_change(sender, instance, **kwargs):
    clear_landing_cache()


@receiver(post_delete, sender=DocumentFeedback)
def clear_landing_cache_on_document_feedback_delete(sender, instance, **kwargs):
    clear_landing_cache()


@receiver(post_save, sender=AboutSystem)
def clear_landing_cache_on_about_system_change(sender, instance, **kwargs):
    clear_landing_cache()


@receiver(post_delete, sender=AboutSystem)
def clear_landing_cache_on_about_system_delete(sender, instance, **kwargs):
    clear_landing_cache()

