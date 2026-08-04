#!/bin/sh
# Kleos — amorçage du conteneur.
#
# L'atelier résout TOUT depuis la racine du site (`_ROOT` dans atelier, cv_letter,
# cv_docx, profile_pipeline). Le mutable et l'immuable y cohabitent :
#
#   immuable (l'IMAGE fait foi)  : tools/ cv/ letters/ assets/
#   mutable  (le VOLUME fait foi): profile.json, data/
#
# D'où ce partage à chaque démarrage. Un simple `cp` unique à la première création
# figerait le code à la version du jour où le volume est né : une mise à jour
# d'image ne changerait plus rien, et le bug se manifesterait comme « le correctif
# n'a pas été déployé » alors qu'il l'aurait été.
#
# Le lien symbolique — plus court à écrire — est EXCLU : `profile_pipeline` écrit
# par `tmp.replace(profile_path)`, un remplacement atomique qui substitue un vrai
# fichier au lien. La persistance disparaîtrait alors en silence, au premier
# enregistrement, sans aucune erreur.
set -eu

mkdir -p /site /site/data

# Code et gabarits : l'image écrase, toujours.
for d in tools cv letters assets; do
  [ -d "/seed/$d" ] && cp -a "/seed/$d" /site/
done

# Profil : la graine ne sert qu'à la toute première naissance du volume.
if [ ! -f /site/profile.json ]; then
  cp /seed/profile.json /site/profile.json
  echo "[kleos] volume vierge — profil initialisé depuis la graine de l'image"
else
  echo "[kleos] profil existant conservé ($(wc -c < /site/profile.json) octets)"
fi

exec python /site/tools/cv/atelier.py
