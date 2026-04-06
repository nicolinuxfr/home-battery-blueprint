# home-battery-blueprint

Projet de blueprint Home Assistant multilingue pour piloter jusqu'à quatre batteries à partir d'un seul capteur de puissance maison. Le blueprint se concentre sur la décharge, peut absorber un export réel via une charge opportuniste, et pilote chaque batterie uniquement via des actions personnalisées. Chaque batterie est rangée dans sa propre section repliée par défaut pour garder un formulaire compact.

Ce blueprint est volontairement générique. Il n'essaie pas d'unifier les APIs propres à chaque marque. À la place, chaque slot batterie activé est piloté par :

- des actions personnalisées pour la décharge et/ou la charge
- des actions d'arrêt optionnelles pour forcer le retour à neutre quand le mode change ou que le blueprint est bloqué
- des helpers ou services spécifiques à une intégration, cachés derrière ces actions quand une marque a besoin d'une surface de contrôle intermédiaire

[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fraw.githubusercontent.com%2Fnicolinuxfr%2Fhome-battery-blueprint%2Fgh-pages%2Ffr%2Fhome_battery_manager.yaml)

URL brute d'import :

`https://raw.githubusercontent.com/nicolinuxfr/home-battery-blueprint/gh-pages/fr/home_battery_manager.yaml`

## Configuration

- `Capteur de puissance maison` : capteur principal utilisé par l'algorithme. Il doit suivre la convention `import > 0` et `export < 0`.
- `Entités de blocage` : liste optionnelle d'entités `binary_sensor` ou `input_boolean`. Le blueprint tourne seulement si toutes les entités sélectionnées sont à `off`. Si l'une passe à `on`, `unknown` ou `unavailable`, toutes les batteries gérées reviennent à neutre et toutes les actions d'arrêt sont exécutées.

Pour chaque slot batterie :

- `Capteur d'état de charge` : laisser vide désactive le slot. Le sélecteur n'affiche que les capteurs de batterie qui remontent un pourcentage. Si tu le renseignes, le slot doit aussi exposer au moins une direction exploitable : une puissance maximale non nulle et l'action `set` correspondante.
- `Puissance maximale de décharge` et `Puissance maximale de charge` : limites manuelles utilisées par l'algorithme.
- `Prioritaire en décharge` : les batteries prioritaires se vident d'abord ; la charge opportuniste préfère d'abord les batteries non prioritaires.
- `Cooldown de commande` : délai anti-spam par batterie pour les actions `set` uniquement. Mets `0` pour le désactiver.
- `Actions de mise en décharge` et `Actions de mise en charge` : obligatoires pour toute direction activée avec une puissance max non nulle. Elles reçoivent des variables d'exécution comme `battery_slot`, `battery_soc`, `target_discharge_w`, `target_charge_w`, `house_power_w` et `export_surplus_w`.
- `Actions d'arrêt de décharge` et `Actions d'arrêt de charge` : hooks optionnels de retour à neutre. Ils sont fortement recommandés pour les batteries pilotées uniquement par actions afin de forcer un état sûr.

Exemple Zendure :

- crée un helper signé tel que `input_number.zendure_virtual_p1`
- configure l'option `p1meter` de l'intégration Zendure sur ce helper
- dans `Actions de mise en décharge`, écris la valeur positive `target_discharge_w` dans le helper
- dans `Actions de mise en charge`, écris la valeur négative `target_charge_w` dans le helper
- dans les deux actions d'arrêt, écris `0`

## Fonctionnement

- À chaque run, le blueprint choisit un seul mode exclusif : `discharge`, `charge` ou `neutral`.
- En décharge, il répartit `max(house_power, 0)` entre les batteries, en privilégiant d'abord les batteries marquées prioritaires puis en triant par pourcentage de charge décroissant.
- En charge opportuniste, il détecte un export réel, exige qu'au moins une batterie soit à `99 %` ou plus, puis remplit les batteries chargeables du SOC le plus bas vers le plus haut, en évitant autant que possible les batteries prioritaires en décharge.
- Une bande morte interne fixe de `50 W` filtre les très petits écarts et évite les écritures inutiles ou les actions répétées. Elle remplace les anciens réglages visibles `Marge de décharge` et `Delta minimal de commande`.
- La sécurité passe avant tout : passer en charge coupe d'abord tous les chemins de décharge gérés, et passer en décharge coupe d'abord tous les chemins de charge gérés. Le blueprint ne cherche jamais à faire charger et décharger en même temps des batteries qu'il pilote lui-même.
- Les actions d'arrêt servent à forcer un retour à neutre quand le mode change, quand une entité de blocage s'active, ou quand le capteur maison devient invalide. Cela évite qu'une intégration pilotée par actions conserve une ancienne consigne.
- Si un slot activé est incomplet, l'automatisation s'arrête maintenant avec un message de validation explicite indiquant si des actions manquent, si les deux puissances sont à `0 W`, ou si les actions et les puissances configurées ne correspondent pas.
- Le cooldown ne limite que les actions `set`. Les actions `stop` l'ignorent volontairement pour pouvoir forcer un retour à neutre immédiatement.

## Limites connues

- Le blueprint ne crée pas lui-même de capteur de moyenne glissante. Si tu veux un signal lissé, fournis en entrée un capteur déjà filtré.
- Pour les batteries pilotées uniquement par actions, les actions d'arrêt devraient être idempotentes, car le blueprint peut devoir les rejouer pour la sécurité.
- Les métadonnées du blueprint et la documentation pointent vers `nicolinuxfr/home-battery-blueprint`.
