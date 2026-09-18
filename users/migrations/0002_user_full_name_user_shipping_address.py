"""
Migration: Add full_name and shipping_address to User model.

Phase 4 — these fields store buyer delivery information, which remains
masked until post-auction settlement is verified (Rule 4).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='full_name',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Full name for delivery / display purposes.',
                max_length=255,
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='shipping_address',
            field=models.TextField(
                blank=True,
                default='',
                help_text='Delivery address. Remains masked until post-auction settlement.',
            ),
        ),
    ]
