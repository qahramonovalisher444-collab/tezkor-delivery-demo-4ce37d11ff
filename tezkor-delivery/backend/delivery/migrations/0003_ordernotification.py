import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('delivery', '0002_order_request_fingerprint_order_request_id_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='OrderNotification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('chat_id', models.BigIntegerField()),
                ('text', models.TextField()),
                ('status', models.CharField(choices=[('pending', 'Kutilmoqda'), ('processing', 'Yuborilmoqda'), ('sent', 'Yuborildi'), ('failed', 'Xato')], default='pending', max_length=12)),
                ('attempts', models.PositiveSmallIntegerField(default=0)),
                ('next_attempt_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('locked_at', models.DateTimeField(blank=True, null=True)),
                ('lock_token', models.UUIDField(blank=True, null=True)),
                ('last_error', models.CharField(blank=True, max_length=240)),
                ('message_id', models.BigIntegerField(blank=True, null=True)),
                ('sent_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('event', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='notification', to='delivery.orderevent')),
            ],
            options={
                'ordering': ['-created_at', '-id'],
                'indexes': [models.Index(fields=['status', 'next_attempt_at'], name='delivery_or_status_ada811_idx')],
            },
        ),
    ]
