.PHONY: extract update compile init

# Paths
LOCALEDIR = text_calcio/locale
POTFILE = messages.pot

# Extract messages
extract:
	pybabel extract -F babel.cfg -o $(POTFILE) .

# Update all .po files
update:
	pybabel update -i $(POTFILE) -d $(LOCALEDIR)

# Compile .po files to .mo files
compile:
	pybabel compile -d $(LOCALEDIR)

# Initialize a new language (usage: make init lang=es)
init:
	pybabel init -i $(POTFILE) -d $(LOCALEDIR) -l $(lang)
