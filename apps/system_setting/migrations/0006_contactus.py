from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('system_setting', '0005_dashboardsettings_credits_text_template_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='ContactUs',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=120)),
                ('email', models.EmailField(max_length=254)),
                ('purpose', models.CharField(choices=[('general_inquiry', 'General Inquiry'), ('support', 'Support'), ('feedback', 'Feedback'), ('refund_request', 'Refund Request'), ('others', 'Others')], max_length=30)),
                ('message', models.TextField()),
                ('status', models.CharField(choices=[('new', 'New'), ('in_progress', 'In Progress'), ('resolved', 'Resolved')], default='new', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
