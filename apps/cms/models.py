from django.db import models
from django.utils.text import slugify

class Page(models.Model):
    class Type(models.TextChoices):
        ABOUT_US = 'about_us', 'About Us'
        PRIVACY_POLICY = 'privacy_policy', 'Privacy Policy'
        TERMS_AND_CONDITIONS = 'terms_and_conditions', 'Terms and Conditions'
        COOKIE_POLICY = 'cookie_policy', 'Cookie Policy'
        IMPRINT = 'imprint', 'Imprint'

    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, blank=True)
    content = models.TextField()
    image = models.ImageField(upload_to='cms/page_banners/', blank=True, null=True)
    type = models.CharField(max_length=50, choices=Type.choices)
    status = models.BooleanField(default=True)


    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class CMS(models.Model):
    page = models.CharField(max_length=255, blank=True, null=True)
    section = models.CharField(max_length=255, blank=True, null=True)
    title = models.CharField(max_length=255, blank=True, null=True)
    sub_title = models.TextField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    short_description = models.TextField(blank=True, null=True)
    background_image = models.ImageField(upload_to='cms/background/', blank=True, null=True)
    file_url = models.FileField(upload_to='cms/files/', blank=True, null=True)
    video_link = models.URLField(blank=True, null=True)
    video_thumbnail = models.ImageField(upload_to='cms/video_thumbnails/', blank=True, null=True, help_text='Thumbnail image for video sections')
    preview_image_1 = models.ImageField(upload_to='cms/preview_samples/', blank=True, null=True)
    preview_image_2 = models.ImageField(upload_to='cms/preview_samples/', blank=True, null=True)
    preview_image_3 = models.ImageField(upload_to='cms/preview_samples/', blank=True, null=True)
    button_text = models.CharField(max_length=255, blank=True, null=True)
    button_link = models.CharField(max_length=255, blank=True, null=True)
    other = models.CharField(max_length=255, blank=True, null=True)

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ]
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='active'
    )

    def __str__(self):
        return self.title or 'Page'
    


class CMSPoint(models.Model):
    cms = models.ForeignKey(CMS, related_name='points', on_delete=models.CASCADE)
    text = models.TextField(help_text=" A key point or feature to be displayed on the page.")
    order = models.PositiveIntegerField(default=0, help_text="The order in which this point should be displayed. Lower numbers are displayed first.")

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.text[:50]


class FAQ(models.Model):
    question = models.CharField(max_length=255)
    answer = models.TextField()
    status = models.BooleanField(default=True)

    def __str__(self):
        return self.question