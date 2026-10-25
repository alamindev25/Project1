from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0008_userprofile_github_userprofile_linkedin_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='address',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
