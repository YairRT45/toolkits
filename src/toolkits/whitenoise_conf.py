from whitenoise import WhiteNoise
from django.conf import settings

class MediaWhiteNoise(WhiteNoise):
    def __init__(self, application, *args, **kwargs):
        
        kwargs.setdefault('autorefresh', True)
        super().__init__(application, *args, **kwargs)
        self.add_files(settings.MEDIA_ROOT, prefix='/media/')