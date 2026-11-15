import delivery.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('delivery', '0004_ordernotification_retry_after_until'),
    ]

    operations = [
        migrations.AlterField(
            model_name='product',
            name='image_url',
            field=models.CharField(blank=True, max_length=600, validators=[delivery.validators.validate_image_url]),
        ),
    ]
