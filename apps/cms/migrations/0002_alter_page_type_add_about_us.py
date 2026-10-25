from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cms", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="page",
            name="type",
            field=models.CharField(
                choices=[
                    ("about_us", "About Us"),
                    ("privacy_policy", "Privacy Policy"),
                    ("terms_and_conditions", "Terms and Conditions"),
                    ("cookie_policy", "Cookie Policy"),
                    ("imprint", "Imprint"),
                ],
                max_length=50,
            ),
        ),
    ]
