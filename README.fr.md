# home-battery-blueprint

Projet de blueprint Home Assistant multilingue pour piloter jusqu'à quatre batteries à partir d'un seul capteur de puissance maison. Le blueprint se concentre sur la décharge, peut absorber un export réel via une charge opportuniste, et écrit pour chaque batterie une consigne de puissance signée dans une entité numérique. Des actions optionnelles restent disponibles pour les intégrations qui ont besoin d'un mode ou d'un service séparé. Chaque batterie est rangée dans sa propre section repliée par défaut pour garder un formulaire compact.

Ce blueprint est volontairement générique. Il n'essaie pas d'unifier les APIs propres à chaque marque. À la place, chaque slot batterie activé est piloté par :

- une entité numérique de consigne signée, mise à jour par le blueprint
- des actions personnalisées optionnelles pour la charge et/ou la décharge quand une intégration a besoin d'un mode séparé
- un helper signé ou une entité de device directe, selon ce que l'intégration accepte réellement

[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fraw.githubusercontent.com%2Fnicolinuxfr%2Fhome-battery-blueprint%2Fgh-pages%2Ffr%2Fhome_battery_manager.yaml)

URL brute d'import :

`https://raw.githubusercontent.com/nicolinuxfr/home-battery-blueprint/gh-pages/fr/home_battery_manager.yaml`

## Configuration

- `Capteur de puissance maison` : capteur principal utilisé par l'algorithme. Le sélecteur n'affiche que les capteurs de puissance, mais Home Assistant ne permet pas de filtrer l'unité ici, donc il faut toujours choisir un capteur signé en `W` avec `import > 0` et `export < 0`.
- `Entités de blocage` : liste optionnelle d'entités `binary_sensor` ou `input_boolean`. Le blueprint tourne seulement si toutes les entités sélectionnées sont à `off`. Si l'une passe à `on`, `unknown` ou `unavailable`, le blueprint peut écrire `0` une seule fois pour neutraliser les batteries gérées sur ce changement d'état précis, puis il arrête toutes les actions personnalisées et ignore les runs bloqués suivants tant que tous les bloqueurs ne sont pas revenus à `off`.

Pour chaque slot batterie :

- `Capteur d'état de charge` : laisser vide désactive le slot. Le sélecteur n'affiche que les capteurs de batterie qui remontent un pourcentage. Si tu le renseignes, le slot doit aussi exposer une entité numérique de consigne et au moins une puissance max non nulle.
- `Capteur de puissance batterie réelle` : optionnel mais fortement recommandé pour les intégrations qui limitent la fréquence des commandes ou appliquent les changements avec retard. Utilise un capteur signé en `W`, positif quand la batterie alimente la maison et négatif quand elle charge. Pendant le cooldown, l'allocateur utilise cette puissance mesurée au lieu de supposer que la dernière consigne est réellement fournie.
- `Puissance maximale de décharge` et `Puissance maximale de charge` : limites manuelles utilisées par l'algorithme.
- `Prioritaire en décharge` : les batteries prioritaires se vident d'abord ; la charge opportuniste préfère d'abord les batteries non prioritaires.
- `Entité de consigne de puissance` : entité `number` ou `input_number` écrite par le blueprint. La consigne est signée : positive en décharge, négative en charge, `0` à l'arrêt. Si tu actives la charge, l'entité choisie doit accepter les valeurs négatives.
- `Cooldown de commande` : délai anti-spam par batterie pour les mises à jour actives de consigne. Mets `0` pour le désactiver. Les passages à `0` et les inversions de signe restent immédiats pour ne pas retarder un arrêt ou un changement de sens. Pendant qu'une batterie est en cooldown, l'allocateur conserve sa consigne active et ne redistribue aux autres batteries que la demande ou le surplus restant.
- `Actions de décharge` et `Actions de charge` : hooks optionnels exécutés à chaque mise à jour active dans le sens correspondant. Ils reçoivent des variables d'exécution comme `battery_slot`, `battery_soc`, `target_power_w`, `target_discharge_w`, `target_charge_w`, `house_power_w` et `export_surplus_w`.

Exemple Zendure :

- crée un helper signé tel que `input_number.zendure_virtual_p1`
- configure l'option `p1meter` de l'intégration Zendure sur ce helper
- renseigne ce helper dans `Entité de consigne de puissance`
- laisse les actions de charge et de décharge vides si l'intégration Zendure consomme déjà ce helper directement

## Fonctionnement

- À chaque run, le blueprint choisit un seul mode exclusif : `discharge`, `charge` ou `neutral`.
- En décharge, il répartit `max(house_power, 0)` entre les batteries, en privilégiant d'abord les batteries marquées prioritaires puis en triant par pourcentage de charge décroissant.
- Quand des capteurs de puissance batterie réelle sont configurés, l'allocateur reconstruit la demande maison sous-jacente en réajoutant la puissance déjà fournie par les batteries gérées. Cela évite que le capteur maison annule artificiellement le travail des batteries et crée des oscillations.
- Si une batterie est encore en cooldown, l'allocateur ne réserve maintenant que la puissance qu'elle délivre réellement lorsqu'un capteur de puissance réelle est configuré. Sans ce capteur, il retombe sur la dernière consigne demandée.
- Si un capteur de puissance réelle reste proche de `0 W` après une consigne non nulle, le blueprint continue temporairement de faire confiance à cette consigne pendant une fenêtre égale à `max(20 s, cooldown de cette batterie)`. Après cela, il cesse d'allouer la charge à cette batterie et laisse une autre batterie prendre le relais.
- Pendant cette même fenêtre, l'allocateur considère temporairement que la dernière consigne non nulle est effective avant de revenir à la puissance mesurée. Cela tient compte de la latence de télémétrie au lieu de couper immédiatement une batterie parce que son capteur n'a pas encore suivi.
- En charge opportuniste, il détecte un export réel, exige qu'au moins une batterie soit à `99 %` ou plus, puis remplit les batteries chargeables du SOC le plus bas vers le plus haut, en évitant autant que possible les batteries prioritaires en décharge.
- Une bande morte interne fixe de `50 W` filtre les très petits écarts et évite les écritures inutiles ou les actions répétées. Elle remplace les anciens réglages visibles `Marge de décharge` et `Delta minimal de commande`.
- La consigne écrite par le blueprint est signée : positive en décharge, négative en charge, `0` en neutre. Un passage à `0`, un capteur invalide, un blocage actif ou une inversion de signe provoquent une écriture immédiate sans attendre le cooldown. Pendant un cooldown actif, le blueprint réserve désormais la puissance déjà commandée sur cette batterie et ne réalloue aux autres batteries que la charge ou le surplus restant.
- Un redémarrage depuis `0` vers le même sens ne contourne plus le cooldown. Cela évite les oscillations rapides où une batterie prioritaire est relâchée pour laisser aider une autre, puis reprend immédiatement la charge au tick suivant.
- Si une entité de consigne refuse une mise à jour, par exemple parce que l'intégration impose son propre délai minimal entre deux changements, l'automatisation continue maintenant et met quand même à jour les autres slots batterie.
- La validation s'exécute maintenant avant toute écriture par batterie ou action personnalisée. Chaque commande non nulle est revérifiée contre l'état courant des entités de blocage juste avant l'exécution, et l'écriture d'un `0` en mode bloqué n'est autorisée que sur le changement d'état du bloqueur lui-même.
- Les actions optionnelles de charge et de décharge tournent uniquement quand la batterie est active dans le sens correspondant. Elles sont utiles pour les intégrations qui ont besoin d'un `select`, d'un service additionnel, ou d'une traduction helper -> API vendor.
- Les étapes internes de l'automatisation portent maintenant des noms explicites pour que les traces Home Assistant affichent plus clairement, pendant le debug, les écritures de consigne par batterie, les hooks de charge/décharge et les arrêts de validation.
- Si un slot activé est incomplet, l'automatisation s'arrête avec un message de validation explicite indiquant s'il manque l'entité de consigne ou si les deux puissances sont à `0 W`.

## Limites connues

- Le blueprint ne crée pas lui-même de capteur de moyenne glissante. Si tu veux un signal lissé, fournis en entrée un capteur déjà filtré.
- Si une batterie doit charger, l'entité de consigne choisie doit accepter les valeurs négatives. Sinon, utilise un helper signé intermédiaire.
- Les actions optionnelles ne tournent pas en neutre. Si ton intégration a besoin d'une traduction explicite du `0`, passe par un helper signé que l'intégration ou une autre automatisation consomme.
- Les métadonnées du blueprint et la documentation pointent vers `nicolinuxfr/home-battery-blueprint`.
