# Generated manually for SRS implementation

import django.db.models.deletion
from django.db import migrations, models


def asignar_numeros_gop(apps, schema_editor):
    Gop = apps.get_model('gestor', 'Gop')
    for toolkit_id in Gop.objects.values_list('toolkit_id', flat=True).distinct():
        for i, gop in enumerate(Gop.objects.filter(toolkit_id=toolkit_id).order_by('id'), start=1):
            gop.numero = i
            gop.save(update_fields=['numero'])


class Migration(migrations.Migration):

    dependencies = [
        ('gestor', '0002_toolkit_fecha_ultima_modificacion'),
    ]

    operations = [
        migrations.AddField(
            model_name='toolkit',
            name='meta',
            field=models.DecimalField(decimal_places=2, default=100.0, max_digits=5),
        ),
        migrations.AlterField(
            model_name='toolkit',
            name='nombre',
            field=models.CharField(max_length=255, unique=True),
        ),
        migrations.AddField(
            model_name='gop',
            name='numero',
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.RunPython(asignar_numeros_gop, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='gop',
            name='numero',
            field=models.PositiveIntegerField(),
        ),
        migrations.AlterModelOptions(
            name='gop',
            options={'ordering': ['numero']},
        ),
        migrations.AlterUniqueTogether(
            name='gop',
            unique_together={('toolkit', 'numero')},
        ),
        migrations.AlterField(
            model_name='gop',
            name='toolkit',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='gops', to='gestor.toolkit'),
        ),
        migrations.AlterField(
            model_name='gop_revision',
            name='comentario',
            field=models.CharField(blank=True, default='', max_length=500),
        ),
        migrations.AlterField(
            model_name='gop_revision',
            name='revision',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='gop_revision_set', to='gestor.revision'),
        ),
        migrations.AlterUniqueTogether(
            name='gop_revision',
            unique_together={('gop', 'revision')},
        ),
        migrations.AlterField(
            model_name='revision',
            name='toolkit',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='revisiones', to='gestor.toolkit'),
        ),
        migrations.AlterUniqueTogether(
            name='revision',
            unique_together={('toolkit', 'fecha_revision', 'linea')},
        ),
        migrations.RenameField(
            model_name='evidencia',
            old_name='evidencia',
            new_name='archivo',
        ),
        migrations.AddField(
            model_name='evidencia',
            name='nombre',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.CreateModel(
            name='PlanAccion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('descripcion', models.TextField()),
                ('responsable', models.CharField(max_length=255)),
                ('fecha_limite', models.DateField()),
                ('completado', models.BooleanField(default=False)),
                ('fecha_creacion', models.DateField(auto_now_add=True)),
                ('gop_revision', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='planes_accion', to='gestor.gop_revision')),
            ],
        ),
    ]
