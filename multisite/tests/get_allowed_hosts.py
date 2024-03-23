def get_allowed_hosts(*extra, replace=None):
    if replace:
        allowed_hosts = []
    else:
        allowed_hosts = [
            ".extrahost.com",
            "app.test1.example.com",
            "app.test2.example.com",
            "example.com",
            "new.app.test3.example.com",
            "test.example.com",
        ]
    allowed_hosts.extend(extra)
    return allowed_hosts
