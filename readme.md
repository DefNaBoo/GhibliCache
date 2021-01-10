# Ghibli Cache test

## Execution du code
Pour executer le serveur utilisez la commande suivante : 

```bash
python ghibly.py
```

Vous devriez voir apparaitre :

```
Updating data :
Starting server :
done __gather_data_from_ghibli_server
done __parse_raw_data
```

Vous pouvez maintenant allez sur votre navigateur pour acceder à la page

http://localhost:8000/movies/

Sur le terminal ou vous avez lancé le serveur vous devriez voir passer la requête

```
127.0.0.1 - - [26/Aug/2020 10:12:56] "GET /movies/ HTTP/1.1" 200 -
```

Toutes les 30 secondes vous devriez voir les lignes suivante : 
```
Updating data :
done __gather_data_from_ghibli_server
done __parse_raw_data
```
Ces lignes vous indiquent que le cache s'est bien rafraichi.

Pour quitter le serveur vous devez faire Ctrl+C sur le terminal.

Il y'a d'autre informations sous forme de commentaire dans le code.

## Test unitaire

Je n'ai pas beacoup ecrit de tests unitaires mais j'ai mis un exemple de test pour
le code du Thread qui met a jour les données toutes les x secondes.

Pour lancer les test vous devez faire :
```bash
python -m unittest ghibli.py
```

Vous allez voir les deux test s'executer : 
```bash
..
----------------------------------------------------------------------
Ran 2 tests in 0.302s

OK
```

## Conclusion
Je pense avoir passez trop de temps dessus :D, je me suis laissé prendre par le jeu.

Il y'a plein d'elements à améliorer dans le code. La premiere est d'éclater le code
en plusieurs fichiers. J'ai maintenanu le code sur un fichier car je trouvais ca plus simple
pour vous à lire.

Je n'ai aussi utilisé que la librairie de python standard pour ne pas avoir de dépendance et
que cela soit simple à exécuter.
La classe ThreadingHTTPServer, par exemple, n'est ni pratique ni efficace a utilisé mais elle
ne depend de rien d'autre que la librairie standard.

Si on devait utiliser ce logiciel en production je préférerai passer sous Flask. L'utilisation
de django est aussi possible mais nous n'avons pas besoin de toute la stack.

Bien sur le taux de couverture des tests unitaires est ridicule, en temps normal les tests devraient
couvrir tout le code.

J'éspere que vous prendrez plaisir a lire le code.



