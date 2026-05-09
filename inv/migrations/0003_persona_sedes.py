from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inv', '0002_software_activo'),
    ]

    operations = [
        migrations.AddField(
            model_name='persona',
            name='sedes',
            field=models.ManyToManyField(
                blank=True,
                related_name='personas',
                to='inv.sede',
                verbose_name='Sedes asignadas',
            ),
        ),
    ]
