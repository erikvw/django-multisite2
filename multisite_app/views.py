from django.http import HttpResponse


def domain_view(request):
    site_id = request.site.id
    domain = request.site.domain
    html = f"<html><body>{site_id}@{domain}</body></html>"
    return HttpResponse(html)
