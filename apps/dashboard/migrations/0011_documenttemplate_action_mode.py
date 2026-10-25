from django.db import migrations, models


def _sync_action_mode_from_base_content(apps, schema_editor):
    DocumentTemplate = apps.get_model("dashboard", "DocumentTemplate")

    for template in DocumentTemplate.objects.all().only("id", "base_content"):
        actions = (template.base_content or {}).get("actions", {})
        allow_email = bool(actions.get("send_via_email", True))
        allow_signature = bool(actions.get("send_for_signature", False))

        if allow_email and allow_signature:
            mode = "both"
        elif allow_email:
            mode = "email_only"
        elif allow_signature:
            mode = "signature_only"
        else:
            mode = "preview_download_only"

        DocumentTemplate.objects.filter(id=template.id).update(action_mode=mode)


class Migration(migrations.Migration):

    dependencies = [
        ("dashboard", "0010_documenttemplate_content_template_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="documenttemplate",
            name="action_mode",
            field=models.CharField(
                choices=[
                    ("preview_download_only", "Preview + Download only"),
                    ("email_only", "Preview + Download + Send by Email"),
                    ("signature_only", "Preview + Download + Send for Signature"),
                    ("both", "Preview + Download + Email + Signature"),
                ],
                default="both",
                help_text="Controls which post-generation actions are available for this template. Preview and Download are always available.",
                max_length=30,
            ),
        ),
        migrations.RunPython(_sync_action_mode_from_base_content, migrations.RunPython.noop),
    ]
