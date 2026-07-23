from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ReelRoots_app", "0010_userprofile_is_moderator_contributorsubmission_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="reel",
            name="source_url",
            field=models.URLField(blank=True, max_length=2000),
        ),
        migrations.AlterField(
            model_name="reel",
            name="video_url",
            field=models.URLField(max_length=2000),
        ),
        migrations.AlterField(
            model_name="reel",
            name="thumbnail_url",
            field=models.URLField(blank=True, max_length=2000),
        ),
        migrations.AlterField(
            model_name="knowledgesource",
            name="url",
            field=models.URLField(max_length=2000, unique=True),
        ),
        migrations.AlterField(
            model_name="verificationrequest",
            name="source_file",
            field=models.FileField(blank=True, max_length=500, upload_to="verification/submissions/"),
        ),
    ]
