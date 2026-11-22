from django.db import migrations


def add(apps, schema_editor):
    T = apps.get_model("web", "Testimonial")
    if not T.objects.filter(organization="Middlebury Elementary School").exists():
        T.objects.create(
            quote="We would recommend a fundraiser with Roundbelly's without any hesitation.",
            name="Marion Hostetler", role="Principal", organization="Middlebury Elementary School",
            page="fundraising", show=False,
            permission_note="From his thank-you letter, Nov 18, 2024. Ask before showing.")


class Migration(migrations.Migration):
    dependencies = [("web", "0002_testimonials")]
    operations = [migrations.RunPython(add, migrations.RunPython.noop)]
