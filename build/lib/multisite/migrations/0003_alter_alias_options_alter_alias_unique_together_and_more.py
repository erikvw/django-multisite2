# Generated by Django 5.0.3 on 2024-03-22 03:52

import multisite.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("multisite", "0002_alter_alias_id_alter_alias_is_canonical"),
        ("sites", "0002_alter_domain_unique"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="alias",
            options={"verbose_name": "Alias", "verbose_name_plural": "Aliases"},
        ),
        migrations.AlterUniqueTogether(
            name="alias",
            unique_together=set(),
        ),
        migrations.AlterField(
            model_name="alias",
            name="is_canonical",
            field=models.IntegerField(
                default=None,
                editable=False,
                help_text="Does this domain name match the one in site?",
                null=True,
                validators=[multisite.models.validate_1_or_none],
                verbose_name="is canonical?",
            ),
        ),
        migrations.AddConstraint(
            model_name="alias",
            constraint=models.UniqueConstraint(
                fields=("is_canonical", "site"), name="unique_is_canonical_site"
            ),
        ),
    ]
