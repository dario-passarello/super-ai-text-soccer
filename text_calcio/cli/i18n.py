# localization.py
import gettext
import os


# Now, _ can be imported by other modules
def set_language(lang_code = 'it'):
    locale_dir = os.path.join(os.path.dirname(__file__), '..', 'locale')
    gettext.bindtextdomain('messages', locale_dir)
    gettext.textdomain('messages')
    lang_trans = gettext.translation('messages', localedir=locale_dir, languages=[lang_code])
    lang_trans.install()
    global _
    _ = lang_trans.gettext


set_language('it')