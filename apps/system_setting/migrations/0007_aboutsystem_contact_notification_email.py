from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('system_setting', '0006_contactus'),
    ]

    operations = [
        migrations.AddField(
            model_name='aboutsystem',
            name='contact_notification_email',
            field=models.EmailField(blank=True, max_length=254, null=True),
        ),
    ]
