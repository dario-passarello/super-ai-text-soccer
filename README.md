# Super AI Text Soccery


## Internationalization

This program is internazionalized using Babel.

```python
from text_calcio.cli.i18n import _

translatable_string = _('This string is translatable')
```

First extract the strings in a template messages.pot file. 
```bash
make extract
```
Do not add translation in this file

To inizialize a new language translation
```bash
make init lang={language_code}
```

In the text_calcio/locale/{language_code}/LC_MESSAGES" 
you can add your translation. When you are done compile all translation
files witbashh
```bash
make compile
```

When a translation already exist but you added new strings in the program, ypu can
add the new strings in the translation files using
```bash
make extract
make update
```
The new strings will be added in the file maintaining the existing translations.
Then after you added the new translations compile the files as shown above.
