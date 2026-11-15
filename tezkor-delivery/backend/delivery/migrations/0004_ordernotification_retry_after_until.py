from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('delivery', '0003_ordernotification'),
    ]

    operations = [
        migrations.AddField(
            model_name='ordernotification',
            name='retry_after_until',
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
    ]
